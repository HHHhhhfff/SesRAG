import { apiFetch } from '../http'
import type { ModelListResponse } from '../../types/api-v2'
export function listModels() { return apiFetch<ModelListResponse>('/api/v2/models') }
