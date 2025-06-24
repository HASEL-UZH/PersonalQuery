import { Column, Entity } from 'typeorm';
import BaseTrackedEntity from './BaseTrackedEntity';

@Entity({ name: 'window_activity' })
export class WindowActivityEntity extends BaseTrackedEntity {
  @Column('text', { nullable: true })
  windowTitle: string | null;

  @Column('text', { nullable: true })
  processName: string | null;

  @Column('text', { nullable: true })
  processPath: string | null;

  @Column('int', { nullable: true })
  processId: number | null;

  @Column('text', { nullable: true })
  url: string | null;

  @Column('text', { nullable: false })
  activity: string;

  @Column('datetime', { nullable: true })
  tsStart: Date;

  @Column('datetime', { nullable: true })
  tsEnd: Date;

  @Column('integer', { nullable: true })
  durationInSeconds: number | null;
}
