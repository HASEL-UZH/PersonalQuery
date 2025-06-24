export default interface WindowActivityDto {
  id: string;
  windowTitle: string | null;
  processName: string | null;
  processPath: string | null;
  processId: number | null;
  url: string | null;
  activity: string;
  tsStart: Date;
  tsEnd: Date;
  durationInSeconds: number | null;
  createdAt: Date;
  updatedAt: Date;
  deletedAt: Date | null;
}
