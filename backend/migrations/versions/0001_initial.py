"""Initial schema for projects, immutable source snapshots and review results."""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None


def upgrade():
    op.create_table('projects', sa.Column('id', sa.String(36), primary_key=True), sa.Column('name', sa.String(120), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('submissions', sa.Column('id', sa.String(36), primary_key=True), sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False), sa.Column('content_hash', sa.String(64), nullable=False), sa.Column('skipped', sa.JSON(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('source_files', sa.Column('id', sa.String(36), primary_key=True), sa.Column('submission_id', sa.String(36), sa.ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False), sa.Column('path', sa.String(300), nullable=False), sa.Column('content', sa.Text(), nullable=False))
    op.create_table('analysis_jobs', sa.Column('id', sa.String(36), primary_key=True), sa.Column('submission_id', sa.String(36), sa.ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False), sa.Column('status', sa.String(20), nullable=False), sa.Column('stage', sa.String(100), nullable=False), sa.Column('request', sa.JSON(), nullable=False), sa.Column('errors', sa.JSON(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('model_runs', sa.Column('id', sa.String(36), primary_key=True), sa.Column('job_id', sa.String(36), sa.ForeignKey('analysis_jobs.id', ondelete='CASCADE'), nullable=False), sa.Column('model', sa.String(120), nullable=False), sa.Column('status', sa.String(20), nullable=False), sa.Column('metrics', sa.JSON(), nullable=False), sa.Column('coverage', sa.JSON(), nullable=False), sa.Column('raw_response', sa.Text(), nullable=False), sa.Column('error', sa.Text(), nullable=False))
    op.create_table('findings', sa.Column('id', sa.String(36), primary_key=True), sa.Column('run_id', sa.String(36), sa.ForeignKey('model_runs.id', ondelete='CASCADE'), nullable=False), sa.Column('data', sa.JSON(), nullable=False))
    op.create_table('generated_artifacts', sa.Column('id', sa.String(36), primary_key=True), sa.Column('run_id', sa.String(36), sa.ForeignKey('model_runs.id', ondelete='CASCADE'), nullable=False), sa.Column('kind', sa.String(30), nullable=False), sa.Column('data', sa.JSON(), nullable=False))
    op.create_table('finding_feedback', sa.Column('finding_id', sa.String(36), sa.ForeignKey('findings.id', ondelete='CASCADE'), primary_key=True), sa.Column('verdict', sa.String(30), nullable=False))
    for table, column in [('submissions', 'project_id'), ('source_files', 'submission_id'), ('analysis_jobs', 'submission_id'), ('analysis_jobs', 'status'), ('model_runs', 'job_id'), ('findings', 'run_id'), ('generated_artifacts', 'run_id')]:
        op.create_index(f'ix_{table}_{column}', table, [column])


def downgrade():
    for table in ['finding_feedback', 'generated_artifacts', 'findings', 'model_runs', 'analysis_jobs', 'source_files', 'submissions', 'projects']:
        op.drop_table(table)
