"""
Pipeline test script.
Usage:
    python test_pipeline.py --hf  https://your-space.hf.space
    python test_pipeline.py --hf  https://your-space.hf.space \
                            --railway https://your-app.railway.app
    python test_pipeline.py --hf  https://your-space.hf.space --local
"""

import argparse, sys, time
import requests

SAMPLE_IMAGE = "/home/adham/thesis_1/Radish_images/Radish flea beetle/IMG_20240108_175951_230.jpg"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

def ok(msg):   print(f"{GREEN}  PASS{RESET}  {msg}")
def fail(msg): print(f"{RED}  FAIL{RESET}  {msg}"); sys.exit(1)
def info(msg): print(f"{YELLOW}  ----{RESET}  {msg}")


def predict(base_url, temperature, humidity, soil_moisture, device_id="test_node", image_path=SAMPLE_IMAGE):
    with open(image_path, "rb") as f:
        r = requests.post(
            f"{base_url}/predict",
            data={"temperature": temperature, "humidity": humidity,
                  "soil_moisture": soil_moisture, "device_id": device_id},
            files={"image": f},
            timeout=30,
        )
    r.raise_for_status()
    return r.json()


def delete_session(base_url, device_id):
    requests.delete(f"{base_url}/session/{device_id}", timeout=10)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_health(base_url, label):
    print(f"\n[1] Health check — {label}")
    r = requests.get(f"{base_url}/health", timeout=10)
    assert r.status_code == 200 and r.json().get("status") == "ok", r.text
    ok(f"{label} /health → {r.json()}")


def test_basic_predict(base_url, label):
    print(f"\n[2] Basic predict — {label}")
    delete_session(base_url, "basic_test")
    resp = predict(base_url, temperature=22.0, humidity=60.0,
                   soil_moisture=55.0, device_id="basic_test")

    required = {"action", "action_id", "action_probs", "irrigation_ml",
                "disease", "disease_id", "vision_probs"}
    missing = required - resp.keys()
    assert not missing, f"Missing keys: {missing}"

    assert resp["action"] in ("do_nothing", "irrigate", "fungicide", "pesticide")
    assert len(resp["action_probs"]) == 4
    assert len(resp["vision_probs"]) == 5
    assert abs(sum(resp["vision_probs"]) - 1.0) < 1e-3, "vision_probs must sum to 1"
    assert resp["irrigation_ml"] == 0 or resp["action"] == "irrigate"

    ok(f"action={resp['action']}  disease={resp['disease']}  irrigation_ml={resp['irrigation_ml']}ml")


def test_drought_override(base_url, label):
    print(f"\n[3] Drought sensor override — {label}")
    delete_session(base_url, "drought_test")
    resp = predict(base_url, temperature=30.0, humidity=40.0,
                   soil_moisture=20.0, device_id="drought_test")

    assert resp["disease"] == "drought",       f"Expected drought, got {resp['disease']}"
    assert resp["disease_id"] == 3,            f"Expected disease_id=3, got {resp['disease_id']}"
    assert abs(resp["vision_probs"][3] - 0.96) < 1e-3, "vision_probs[3] should be 0.96"
    assert resp["action"] == "irrigate",       f"Expected irrigate, got {resp['action']}"
    assert resp["irrigation_ml"] > 0,          "irrigation_ml should be > 0 for drought"

    ok(f"disease=drought  action=irrigate  irrigation_ml={resp['irrigation_ml']}ml")


def test_overwatered_override(base_url, label):
    print(f"\n[4] Overwatered sensor override — {label}")
    delete_session(base_url, "overwater_test")
    resp = predict(base_url, temperature=20.0, humidity=80.0,
                   soil_moisture=95.0, device_id="overwater_test")

    assert resp["disease"] == "overwatered",   f"Expected overwatered, got {resp['disease']}"
    assert resp["disease_id"] == 4,            f"Expected disease_id=4, got {resp['disease_id']}"
    assert abs(resp["vision_probs"][4] - 0.96) < 1e-3, "vision_probs[4] should be 0.96"
    assert resp["action"] != "irrigate",       "Should NOT irrigate when overwatered"
    assert resp["irrigation_ml"] == 0,         "irrigation_ml should be 0 when not irrigating"

    ok(f"disease=overwatered  action={resp['action']}  irrigation_ml=0ml")


def test_irrigation_amount(base_url, label):
    print(f"\n[5] Irrigation amount calculation — {label}")
    # Force drought so irrigate is always chosen
    for moisture, expected_ml in [(20.0, 600), (50.0, 300), (70.0, 100)]:
        delete_session(base_url, f"irr_test_{moisture}")
        resp = predict(base_url, temperature=30.0, humidity=35.0,
                       soil_moisture=moisture, device_id=f"irr_test_{moisture}")
        if resp["action"] == "irrigate":
            assert resp["irrigation_ml"] == expected_ml, \
                f"moisture={moisture} → expected {expected_ml}ml, got {resp['irrigation_ml']}ml"
            ok(f"moisture={moisture}% → irrigation_ml={resp['irrigation_ml']}ml")
        else:
            info(f"moisture={moisture}% → action={resp['action']} (PPO chose not to irrigate)")


def test_rolling_window(base_url, label):
    print(f"\n[6] Rolling window / session state — {label}")
    delete_session(base_url, "window_test")

    # Simulate plant drying out over 7 days
    readings = [
        (22, 65, 75),
        (23, 62, 68),
        (25, 58, 55),
        (27, 50, 40),
        (29, 42, 28),
        (30, 38, 20),
        (28, 40, 18),
    ]

    actions = []
    for i, (temp, hum, moist) in enumerate(readings):
        resp = predict(base_url, temperature=temp, humidity=hum,
                       soil_moisture=moist, device_id="window_test")
        actions.append(resp["action"])
        info(f"Day {i+1}: moisture={moist}%  action={resp['action']}  "
             f"disease={resp['disease']}  irrigation_ml={resp['irrigation_ml']}ml")

    # By day 6/7 soil_moisture is 20/18 — should be irrigating
    assert "irrigate" in actions[-2:], \
        f"Expected irrigate in last 2 days, got {actions[-2:]}"
    ok("LSTM correctly recommends irrigate as plant dries out")


def test_session_reset(base_url, label):
    print(f"\n[7] Session reset — {label}")
    # Prime a session with drought readings
    for _ in range(3):
        predict(base_url, temperature=30.0, humidity=35.0,
                soil_moisture=20.0, device_id="reset_test")

    # Reset
    r = requests.delete(f"{base_url}/session/reset_test", timeout=10)
    assert r.status_code == 200
    assert r.json().get("reset") == "reset_test"

    # After reset, session should cold-start (window filled with current reading)
    resp = predict(base_url, temperature=22.0, humidity=60.0,
                   soil_moisture=55.0, device_id="reset_test")
    ok(f"Session reset OK  action={resp['action']}  disease={resp['disease']}")


def test_railway_forwards_to_hf(railway_url, hf_url):
    print(f"\n[8] Railway → HuggingFace forwarding")
    delete_session(railway_url, "fwd_test")
    delete_session(hf_url,      "fwd_test")

    r_resp = predict(railway_url, temperature=22.0, humidity=60.0,
                     soil_moisture=55.0, device_id="fwd_test")
    h_resp = predict(hf_url,      temperature=22.0, humidity=60.0,
                     soil_moisture=55.0, device_id="fwd_test")

    assert r_resp["action"]     == h_resp["action"],     "action mismatch"
    assert r_resp["disease"]    == h_resp["disease"],    "disease mismatch"
    assert r_resp["disease_id"] == h_resp["disease_id"], "disease_id mismatch"
    ok(f"Railway and HF return identical results: action={r_resp['action']}  disease={r_resp['disease']}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hf",      required=True,  help="HuggingFace Space base URL")
    parser.add_argument("--railway", default=None,   help="Railway app base URL")
    parser.add_argument("--local",   action="store_true", help="Also test localhost:7860")
    args = parser.parse_args()

    targets = [args.hf.rstrip("/")]
    labels  = ["HuggingFace"]

    if args.local:
        targets.append("http://localhost:7860")
        labels.append("Local")

    for url, label in zip(targets, labels):
        print(f"\n{'='*55}")
        print(f"  Testing: {label}  ({url})")
        print(f"{'='*55}")
        try:
            test_health(url, label)
            test_basic_predict(url, label)
            test_drought_override(url, label)
            test_overwatered_override(url, label)
            test_irrigation_amount(url, label)
            test_rolling_window(url, label)
            test_session_reset(url, label)
        except requests.exceptions.ConnectionError:
            fail(f"Could not connect to {url} — is the server running?")
        except AssertionError as e:
            fail(str(e))

    if args.railway:
        print(f"\n{'='*55}")
        print(f"  Testing: Railway → HuggingFace forwarding")
        print(f"{'='*55}")
        try:
            test_railway_forwards_to_hf(args.railway.rstrip("/"), targets[0])
        except requests.exceptions.ConnectionError as e:
            fail(str(e))
        except AssertionError as e:
            fail(str(e))

    print(f"\n{GREEN}All tests passed.{RESET}\n")


if __name__ == "__main__":
    main()
