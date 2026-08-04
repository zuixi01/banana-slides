"""Desktop-only startup compatibility helpers."""
import logging
from sqlalchemy import inspect as sqlalchemy_inspect, text


def repair_desktop_settings_schema(db):
    """Repair columns for desktop databases created by older builds."""
    repair_specs = {
        'settings': {
            'ai_provider_format': 'VARCHAR(20)',
            'api_base_url': 'VARCHAR(500)',
            'api_key': 'VARCHAR(500)',
            'image_resolution': 'VARCHAR(20)',
            'image_aspect_ratio': 'VARCHAR(10)',
            'max_description_workers': 'INTEGER',
            'max_image_workers': 'INTEGER',
            'text_model': 'VARCHAR(100)',
            'image_model': 'VARCHAR(100)',
            'mineru_api_base': 'VARCHAR(255)',
            'mineru_token': 'VARCHAR(500)',
            'image_caption_model': 'VARCHAR(100)',
            'output_language': 'VARCHAR(10)',
            'enable_text_reasoning': 'BOOLEAN NOT NULL DEFAULT 0',
            'text_thinking_budget': 'INTEGER NOT NULL DEFAULT 1024',
            'enable_image_reasoning': 'BOOLEAN NOT NULL DEFAULT 0',
            'image_thinking_budget': 'INTEGER NOT NULL DEFAULT 1024',
            'enable_image_quality_control': 'BOOLEAN NOT NULL DEFAULT 0',
            'elevenlabs_enabled': 'BOOLEAN NOT NULL DEFAULT 0',
            'elevenlabs_api_key': 'VARCHAR(500)',
            'elevenlabs_voice_id': 'VARCHAR(100)',
            'openai_image_api_protocol': 'VARCHAR(10)',
            'description_generation_mode': 'VARCHAR(20)',
            'description_extra_fields': 'TEXT',
            'image_prompt_extra_fields': 'TEXT',
            'baidu_api_key': 'VARCHAR(500)',
            'text_model_source': 'VARCHAR(50)',
            'image_model_source': 'VARCHAR(50)',
            'image_caption_model_source': 'VARCHAR(50)',
            'lazyllm_api_keys': 'TEXT',
            'text_api_key': 'VARCHAR(500)',
            'text_api_base_url': 'VARCHAR(500)',
            'image_api_key': 'VARCHAR(500)',
            'image_api_base_url': 'VARCHAR(500)',
            'image_caption_api_key': 'VARCHAR(500)',
            'image_caption_api_base_url': 'VARCHAR(500)',
            'openai_oauth_access_token': 'TEXT',
            'openai_oauth_refresh_token': 'TEXT',
            'openai_oauth_expires_at': 'DATETIME',
            'openai_oauth_account_id': 'VARCHAR(100)',
            'created_at': 'DATETIME',
            'updated_at': 'DATETIME',
        },
        'projects': {
            'workspace_id': "VARCHAR(36) NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002'",
            'project_title': 'VARCHAR(255)',
            'outline_requirements': 'TEXT',
            'description_requirements': 'TEXT',
            'template_style': 'TEXT',
            'template_mode': "VARCHAR(20) DEFAULT 'single'",
            'export_extractor_method': "VARCHAR(50) DEFAULT 'hybrid'",
            'export_inpaint_method': "VARCHAR(50) DEFAULT 'hybrid'",
            'export_allow_partial': 'BOOLEAN DEFAULT 0',
            'enable_icon_subject_extraction': 'BOOLEAN DEFAULT 1',
            'image_aspect_ratio': "VARCHAR(10) DEFAULT '16:9'",
            'current_outline_version_id': 'VARCHAR(36)',
            'confirmed_outline_version_id': 'VARCHAR(36)',
            'descriptions_confirmed_at': 'DATETIME',
        },
        'pages': {
            'previous_description_content': 'TEXT',
            'image_stale': 'BOOLEAN NOT NULL DEFAULT 0',
            'cached_image_path': 'VARCHAR(500)',
            'narration_text': 'TEXT',
            'template_asset_id': 'VARCHAR(36)',
            'template_style_text': 'TEXT',
            'template_selection_source': 'VARCHAR(20)',
            'template_match_reason': 'TEXT',
            'template_match_confidence': 'FLOAT',
        },
        'user_templates': {
            'thumb_path': 'VARCHAR(500)',
            'file_size': 'INTEGER',
        },
        'materials': {
            'workspace_id': "VARCHAR(36) NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002'",
            'caption': 'VARCHAR(500)',
            'original_filename': 'VARCHAR(500)',
        },
        'reference_files': {
            'workspace_id': "VARCHAR(36) NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002'",
            'mineru_batch_id': 'VARCHAR(100)',
        },
        'tasks': {
            'workspace_id': "VARCHAR(36) NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002'",
            'idempotency_key': 'VARCHAR(100)',
            'completed_at': 'DATETIME',
        },
        'user_style_templates': {
            'color': 'VARCHAR(20)',
        },
    }

    repaired = {}
    with db.engine.begin() as conn:
        inspector = sqlalchemy_inspect(conn)
        existing_tables = set(inspector.get_table_names())
        for table_name, required_columns in repair_specs.items():
            if table_name not in existing_tables:
                continue
            existing_columns = {column['name'] for column in inspector.get_columns(table_name)}
            for column_name, column_type in required_columns.items():
                if column_name in existing_columns:
                    continue
                conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}'))
                repaired.setdefault(table_name, []).append(column_name)

        settings_columns = set()
        if 'settings' in existing_tables:
            settings_columns = {column['name'] for column in inspector.get_columns('settings')}
        if 'baidu_api_key' in repaired.get('settings', []) and 'baidu_ocr_api_key' in settings_columns:
            conn.execute(text(
                'UPDATE settings SET baidu_api_key = baidu_ocr_api_key '
                'WHERE baidu_api_key IS NULL AND baidu_ocr_api_key IS NOT NULL'
            ))

        # db.create_all creates these tables for fresh desktop installs; seed
        # the local identity after repairing an older database in place.
        if {'users', 'workspaces', 'memberships'}.issubset(existing_tables):
            conn.execute(text(
                "INSERT OR IGNORE INTO users (id,email,display_name,created_at) "
                "VALUES ('00000000-0000-0000-0000-000000000001','local@banana.invalid','Local User',CURRENT_TIMESTAMP)"
            ))
            conn.execute(text(
                "INSERT OR IGNORE INTO workspaces (id,name,slug,owner_user_id,created_at) "
                "VALUES ('00000000-0000-0000-0000-000000000002','Local Workspace','local',"
                "'00000000-0000-0000-0000-000000000001',CURRENT_TIMESTAMP)"
            ))
            conn.execute(text(
                "INSERT OR IGNORE INTO memberships (id,workspace_id,user_id,role,created_at) "
                "VALUES ('00000000-0000-0000-0000-000000000003',"
                "'00000000-0000-0000-0000-000000000002',"
                "'00000000-0000-0000-0000-000000000001','owner',CURRENT_TIMESTAMP)"
            ))

    if repaired:
        details = '; '.join(f"{table}: {', '.join(columns)}" for table, columns in repaired.items())
        logging.info(f"Repaired desktop database schema, added columns: {details}")
