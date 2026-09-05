import { create } from "zustand";

import { api } from "@/lib/api-client";


export type OabEnrollmentType = "principal" | "supplementary" | "transfer" | "other";
export type OabEnrollmentStatus = "planning" | "gathering" | "submitted" | "awaiting_response" | "completed" | "paused";

export type OabSource = {
  uf: string;
  state_name: string;
  official_url: string;
  directory_url: string;
  provision_url: string;
  source_version: string;
  source_checked_at: string;
  notice: string;
};

export type OabChecklistItem = {
  id: string;
  enrollment_id: string;
  title: string;
  notes: string | null;
  is_completed: boolean;
  revision: number;
  created_at: string;
  updated_at: string;
};

export type OabEnrollment = {
  id: string;
  uf: string;
  enrollment_type: OabEnrollmentType;
  status: OabEnrollmentStatus;
  protocol: string | null;
  source_url: string;
  source_version: string;
  source_checked_at: string;
  source_notice: string;
  provision_url: string;
  revision: number;
  created_at: string;
  updated_at: string;
  checklist: OabChecklistItem[];
};

type EnrollmentCreate = {
  request_id: string;
  uf: string;
  enrollment_type: OabEnrollmentType;
  status: OabEnrollmentStatus;
  protocol: string | null;
};

type OabState = {
  sources: OabSource[];
  enrollments: OabEnrollment[];
  loading: boolean;
  saving: boolean;
  error: string;
  load: () => Promise<void>;
  clearError: () => void;
  createEnrollment: (payload: EnrollmentCreate) => Promise<void>;
  updateEnrollment: (enrollment: OabEnrollment, changes: Partial<Pick<OabEnrollment, "uf" | "enrollment_type" | "status" | "protocol">>) => Promise<void>;
  addChecklistItem: (enrollmentId: string, requestId: string, title: string, notes: string) => Promise<void>;
  updateChecklistItem: (enrollmentId: string, item: OabChecklistItem, changes: Partial<Pick<OabChecklistItem, "title" | "notes" | "is_completed">>) => Promise<void>;
  deleteChecklistItem: (enrollmentId: string, item: OabChecklistItem) => Promise<void>;
};

const message = (error: unknown) => error instanceof Error ? error.message : "Não foi possível concluir a operação.";

export const useOabStore = create<OabState>((set, get) => ({
  sources: [],
  enrollments: [],
  loading: true,
  saving: false,
  error: "",

  clearError: () => set({ error: "" }),

  load: async () => {
    set({ loading: true, error: "" });
    try {
      const [sourceList, enrollmentList] = await Promise.all([
        api.get<{ items: OabSource[] }>("/oab/sources"),
        api.get<{ items: OabEnrollment[] }>("/oab/enrollments"),
      ]);
      set({ sources: sourceList.items, enrollments: enrollmentList.items });
    } catch (error) {
      set({ error: message(error) });
    } finally {
      set({ loading: false });
    }
  },

  createEnrollment: async (payload) => {
    set({ saving: true, error: "" });
    try {
      const enrollment = await api.post<OabEnrollment>("/oab/enrollments", payload);
      set({ enrollments: [enrollment, ...get().enrollments] });
    } catch (error) {
      set({ error: message(error) });
      throw error;
    } finally {
      set({ saving: false });
    }
  },

  updateEnrollment: async (current, changes) => {
    set({ saving: true, error: "" });
    try {
      const enrollment = await api.patch<OabEnrollment>(`/oab/enrollments/${current.id}`, {
        ...changes,
        expected_revision: current.revision,
      });
      set({ enrollments: get().enrollments.map(item => item.id === enrollment.id ? enrollment : item) });
    } catch (error) {
      set({ error: message(error) });
      throw error;
    } finally {
      set({ saving: false });
    }
  },

  addChecklistItem: async (enrollmentId, requestId, title, notes) => {
    set({ saving: true, error: "" });
    try {
      const item = await api.post<OabChecklistItem>(`/oab/enrollments/${enrollmentId}/checklist`, {
        request_id: requestId,
        title,
        notes: notes || null,
      });
      set({
        enrollments: get().enrollments.map(enrollment => enrollment.id === enrollmentId
          ? { ...enrollment, checklist: [...enrollment.checklist, item] }
          : enrollment),
      });
    } catch (error) {
      set({ error: message(error) });
      throw error;
    } finally {
      set({ saving: false });
    }
  },

  updateChecklistItem: async (enrollmentId, current, changes) => {
    set({ saving: true, error: "" });
    try {
      const item = await api.patch<OabChecklistItem>(
        `/oab/enrollments/${enrollmentId}/checklist/${current.id}`,
        { ...changes, expected_revision: current.revision },
      );
      set({
        enrollments: get().enrollments.map(enrollment => enrollment.id === enrollmentId
          ? { ...enrollment, checklist: enrollment.checklist.map(row => row.id === item.id ? item : row) }
          : enrollment),
      });
    } catch (error) {
      set({ error: message(error) });
      throw error;
    } finally {
      set({ saving: false });
    }
  },

  deleteChecklistItem: async (enrollmentId, item) => {
    set({ saving: true, error: "" });
    try {
      await api.delete(`/oab/enrollments/${enrollmentId}/checklist/${item.id}?expected_revision=${item.revision}`);
      set({
        enrollments: get().enrollments.map(enrollment => enrollment.id === enrollmentId
          ? { ...enrollment, checklist: enrollment.checklist.filter(row => row.id !== item.id) }
          : enrollment),
      });
    } catch (error) {
      set({ error: message(error) });
      throw error;
    } finally {
      set({ saving: false });
    }
  },
}));
