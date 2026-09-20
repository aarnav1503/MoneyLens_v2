import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import {
  fetchProfile,
  updateProfile,
  fetchSpendingInsights,
  fetchGoals,
  createGoal,
  deleteGoal,
  simulatePurchase,
  simulateEMI,
  sendChatMessage,
  confirmChatAction,
  uploadBankStatement,
  fetchStatementTransactions,
  confirmStatementObservation,
  UserFinancialProfile,
} from "@/lib/api-client";

export function useAuthUser() {
  return useQuery({
    queryKey: ["auth-user"],
    queryFn: async () => {
      // 1. Try real Supabase session (preferred)
      try {
        const { data, error } = await supabase.auth.getUser();
        if (!error && data?.user?.id) {
          return data.user.id;
        }
      } catch {
        // Supabase unreachable — fall through to localStorage
      }

      // 2. Fallback: derive a stable user_id from localStorage email
      const localUser = localStorage.getItem("moneylens_user");
      if (localUser) {
        try {
          const parsed = JSON.parse(localUser);
          const email = parsed.email as string;
          if (email) {
            // Create a deterministic ID from email so the same user always
            // gets the same backend user_id regardless of Supabase availability
            return `local_${email.replace(/[^a-zA-Z0-9]/g, "_")}`;
          }
        } catch {
          // ignore parse error
        }
      }

      throw new Error("Not authenticated");
    },
    staleTime: 1000 * 60 * 5, // 5 mins - don't re-check auth every render
    retry: false,
  });
}

export function useProfile() {
  const { data: userId } = useAuthUser();
  return useQuery({
    queryKey: ["profile", userId],
    queryFn: () => fetchProfile(userId!),
    enabled: !!userId,
    staleTime: 0,
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  const { data: userId } = useAuthUser();
  
  return useMutation({
    mutationFn: (updates: Partial<UserFinancialProfile>) => {
      if (!userId) throw new Error("Not authenticated");
      return updateProfile(updates, userId);
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["profile", userId], data);
      queryClient.invalidateQueries({ queryKey: ["spending", userId] });
      queryClient.invalidateQueries({ queryKey: ["statement_transactions", userId] });
      queryClient.invalidateQueries({ queryKey: ["goals", userId] });
    },
  });
}

export function useSpending() {
  const { data: userId } = useAuthUser();
  return useQuery({
    queryKey: ["spending", userId],
    queryFn: () => fetchSpendingInsights(userId!),
    enabled: !!userId,
    staleTime: 0,
  });
}

export function useStatementTransactions() {
  const { data: userId } = useAuthUser();
  return useQuery({
    queryKey: ["statement_transactions", userId],
    queryFn: () => fetchStatementTransactions(userId!),
    enabled: !!userId,
    staleTime: 0,
  });
}

export function useUploadStatement() {
  const queryClient = useQueryClient();
  const { data: userId } = useAuthUser();
  
  return useMutation({
    mutationFn: ({ file, saveRaw }: { file: File; saveRaw: boolean }) => {
      if (!userId) throw new Error("Not authenticated");
      return uploadBankStatement(file, saveRaw, userId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile", userId] });
      queryClient.invalidateQueries({ queryKey: ["spending", userId] });
      queryClient.invalidateQueries({ queryKey: ["statement_transactions", userId] });
      queryClient.invalidateQueries({ queryKey: ["goals", userId] });
    },
  });
}

export function useConfirmObservation() {
  const queryClient = useQueryClient();
  const { data: userId } = useAuthUser();
  
  return useMutation({
    mutationFn: ({ type, field, value }: { type: string, field: string, value: number }) => {
      if (!userId) throw new Error("Not authenticated");
      return confirmStatementObservation(type, field, value, userId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile", userId] });
      queryClient.invalidateQueries({ queryKey: ["spending", userId] });
      queryClient.invalidateQueries({ queryKey: ["statement_transactions", userId] });
      queryClient.invalidateQueries({ queryKey: ["goals", userId] });
    },
  });
}

export function useGoals() {
  const { data: userId } = useAuthUser();
  return useQuery({
    queryKey: ["goals", userId],
    queryFn: () => fetchGoals(userId!),
    enabled: !!userId,
    staleTime: 0,
  });
}

export function useCreateGoal() {
  const queryClient = useQueryClient();
  const { data: userId } = useAuthUser();
  
  return useMutation({
    mutationFn: (goal: any) => {
      if (!userId) throw new Error("Not authenticated");
      return createGoal(goal, userId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals", userId] });
    },
  });
}

export function useDeleteGoal() {
  const queryClient = useQueryClient();
  const { data: userId } = useAuthUser();
  
  return useMutation({
    mutationFn: (goalId: string) => {
      if (!userId) throw new Error("Not authenticated");
      return deleteGoal(goalId, userId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals", userId] });
    },
  });
}

export function useChatbot() {
  const queryClient = useQueryClient();
  const { data: userId } = useAuthUser();

  const sendMessage = useMutation({
    mutationFn: ({ message, sessionId }: { message: string; sessionId?: string }) => {
      if (!userId) throw new Error("Not authenticated");
      return sendChatMessage(message, sessionId, userId);
    },
  });

  const confirmAction = useMutation({
    mutationFn: ({ actionType, data }: { actionType: "UPDATE_PROFILE" | "CREATE_GOAL"; data: any }) => {
      if (!userId) throw new Error("Not authenticated");
      return confirmChatAction(actionType, data, userId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile", userId] });
      queryClient.invalidateQueries({ queryKey: ["goals", userId] });
      queryClient.invalidateQueries({ queryKey: ["spending", userId] });
      queryClient.invalidateQueries({ queryKey: ["statement_transactions", userId] });
    },
  });

  return { sendMessage, confirmAction };
}
