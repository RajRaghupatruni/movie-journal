DROP FUNCTION IF EXISTS app.clear_user_delivery_state(uuid);
DROP FUNCTION IF EXISTS app.cancel_user_tandem_notifications(uuid,uuid);
DROP FUNCTION IF EXISTS app.insert_notification(uuid,text,uuid,uuid,uuid,uuid,jsonb,text);
CREATE OR REPLACE FUNCTION app.current_user_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid
$$;
ALTER TABLE storage_cleanup_failures DISABLE ROW LEVEL SECURITY;
ALTER TABLE notifications DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cleanup_worker ON storage_cleanup_failures;
DROP POLICY IF EXISTS notifications_service_insert ON notifications;
DROP POLICY IF EXISTS notifications_delete ON notifications;
DROP POLICY IF EXISTS notifications_update ON notifications;
DROP POLICY IF EXISTS notifications_select ON notifications;
