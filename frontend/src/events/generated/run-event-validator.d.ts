// 自动生成自 contracts/run_event_v3.json；运行 npm run generate:events，勿手改。
// Schema SHA-256: 2b67d2092fe3dd8273ec5676b8ba695ea7fb23909d920a18ddc49fb51cd6af5d
import type { RunEvent } from '../../types/api-v3'
declare const validate: (value: unknown) => value is RunEvent
export default validate
export declare const eventKinds: ReadonlyArray<RunEvent['type']>
