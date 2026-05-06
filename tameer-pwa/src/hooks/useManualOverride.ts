import { useMutation, useQueryClient } from '@tanstack/react-query';
import { postManualCommand } from '../api/endpoints';
import type { ManualCommandRequest } from '../types/api';

export const useManualOverride = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ManualCommandRequest) => postManualCommand(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['events'] }),
  });
};
