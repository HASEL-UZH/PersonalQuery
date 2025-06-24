export default interface SessionDto {
  id: string;
  question: string;
  scale: number;
  response: number | null;
  skipped: boolean;
  tsStart: Date;
  tsEnd: Date;
  durationInSeconds: number;
}
