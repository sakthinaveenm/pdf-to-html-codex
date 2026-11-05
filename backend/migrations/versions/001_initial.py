"""Initial durable jobs, revisions and annotations schema."""
from alembic import op
import sqlalchemy as sa
revision='001'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    # Checkfirst supports databases initialized on first application start.
    from app.db.database import Base
    Base.metadata.create_all(op.get_bind(),checkfirst=True)

def downgrade():
    for table in ('annotations','revisions','jobs'):op.drop_table(table)
