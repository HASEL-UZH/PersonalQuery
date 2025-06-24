import { Column, Entity } from 'typeorm';
import BaseTrackedEntity from './BaseTrackedEntity';

@Entity({ name: 'session' })
export class SessionEntity extends BaseTrackedEntity {
  @Column('text', { nullable: true })
  question: string;

  @Column('int', { nullable: true })
  scale: number;

  @Column('int', { nullable: true })
  response: number;

  @Column('boolean', { default: false, nullable: true })
  skipped: boolean;

  @Column('datetime', { precision: 0, nullable: true })
  tsStart: Date;

  @Column('datetime', { precision: 0, nullable: true })
  tsEnd: Date;

  @Column('int')
  durationInSeconds: number;
}
