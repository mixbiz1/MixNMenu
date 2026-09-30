"""Create the common immutable audit event table for MXMN.

Idempotent SQL Server migration. Run only after application code has been updated.
"""
from sqlalchemy import text
from database import engine

SQL = r"""
IF OBJECT_ID(N'dbo.tb_audit_event', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.tb_audit_event (
        audit_event_id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        comp_code NVARCHAR(20) NOT NULL,
        user_id NVARCHAR(50) NOT NULL,
        menu_code NVARCHAR(50) NOT NULL,
        action NVARCHAR(30) NOT NULL,
        entity_type NVARCHAR(50) NOT NULL,
        entity_id NVARCHAR(100) NOT NULL,
        source NVARCHAR(200) NOT NULL,
        before_json NVARCHAR(MAX) NULL,
        after_json NVARCHAR(MAX) NULL,
        reason NVARCHAR(1000) NULL,
        related_entity_type NVARCHAR(50) NULL,
        related_entity_id NVARCHAR(100) NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_tb_audit_event_created_at DEFAULT SYSUTCDATETIME()
    );
    CREATE INDEX IX_tb_audit_event_entity
        ON dbo.tb_audit_event(comp_code, entity_type, entity_id, audit_event_id);
    CREATE INDEX IX_tb_audit_event_created
        ON dbo.tb_audit_event(comp_code, created_at, audit_event_id);
END;
"""

if __name__ == "__main__":
    with engine.begin() as conn:
        conn.execute(text(SQL))
    print("Audit history migration completed.")
