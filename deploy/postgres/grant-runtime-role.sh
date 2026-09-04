#!/bin/sh
set -eu

psql --set=ON_ERROR_STOP=1 \
  --set=db_name="$PGDATABASE" \
  --set=app_user="$POSTGRES_APP_USER" \
  --set=admin_user="$POSTGRES_ADMIN_USER" <<'SQL'
GRANT CONNECT ON DATABASE :"db_name" TO :"app_user";
GRANT USAGE ON SCHEMA public TO :"app_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"app_user";
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO :"app_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"admin_user" IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"admin_user" IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO :"app_user";
REVOKE UPDATE, DELETE ON TABLE audit_logs, notification_events FROM :"app_user";
REVOKE UPDATE, DELETE ON TABLE workspace_document_versions FROM :"app_user";
REVOKE UPDATE, DELETE ON TABLE brand_versions, brand_assets, brand_exports FROM :"app_user";
REVOKE UPDATE, DELETE ON TABLE document_kit_receipts, pilot_feedback, routine_actions FROM :"app_user";
REVOKE DELETE ON TABLE workspace_ledger_entries, case_messages, portal_grants FROM :"app_user";
REVOKE DELETE ON TABLE notification_provider_receipts FROM :"app_user";
GRANT EXECUTE ON FUNCTION notification_tenant_for_provider(text, text) TO :"app_user";
GRANT EXECUTE ON FUNCTION notification_recovery_candidates(integer, integer) TO :"app_user";
GRANT EXECUTE ON FUNCTION push_recovery_candidates(integer, integer) TO :"app_user";
GRANT EXECUTE ON FUNCTION routine_reminder_candidates(integer) TO :"app_user";
GRANT EXECUTE ON FUNCTION tenant_channel_webhook_identity(text) TO :"app_user";
GRANT EXECUTE ON FUNCTION tenant_channel_email_inbound_identity(text) TO :"app_user";
GRANT EXECUTE ON FUNCTION account_token_tenant_for_hash(text, text) TO :"app_user";
GRANT EXECUTE ON FUNCTION team_invitation_tenant_for_hash(text) TO :"app_user";
GRANT EXECUTE ON FUNCTION public_intake_tenant_for_token(text) TO :"app_user";
GRANT EXECUTE ON FUNCTION operation_webhook_identity(text, text, text) TO :"app_user";
GRANT EXECUTE ON FUNCTION controladoria_monitoring_candidates(integer) TO :"app_user";
GRANT EXECUTE ON FUNCTION controladoria_escavador_webhook_targets(text, text) TO :"app_user";
GRANT EXECUTE ON FUNCTION document_lifecycle_candidates(integer) TO :"app_user";
GRANT EXECUTE ON FUNCTION mark_document_object_deleted(text, text, text) TO :"app_user";
GRANT EXECUTE ON FUNCTION calendar_webhook_identity(text, text) TO :"app_user";
GRANT EXECUTE ON FUNCTION calendar_reconciliation_candidates(integer) TO :"app_user";
GRANT EXECUTE ON FUNCTION autentique_signature_event_candidates(integer) TO :"app_user";
GRANT EXECUTE ON FUNCTION clicksign_signature_event_candidates(integer) TO :"app_user";
SQL
