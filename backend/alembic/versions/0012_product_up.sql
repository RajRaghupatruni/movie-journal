CREATE OR REPLACE FUNCTION app.current_user_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
    SELECT u.id FROM public.users u
    WHERE u.id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
      AND u.is_active
$$;

ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications FORCE ROW LEVEL SECURITY;
CREATE POLICY notifications_select ON notifications FOR SELECT
    USING (user_id = app.current_user_id());
CREATE POLICY notifications_update ON notifications FOR UPDATE
    USING (user_id = app.current_user_id()) WITH CHECK (user_id = app.current_user_id());
CREATE POLICY notifications_delete ON notifications FOR DELETE
    USING (user_id = app.current_user_id() OR current_setting('app.notification_mode', true) = 'true');
CREATE POLICY notifications_service_insert ON notifications FOR INSERT
    WITH CHECK (current_setting('app.notification_mode', true) = 'true');

CREATE OR REPLACE FUNCTION app.insert_notification(
    target_user_id uuid, notification_type text, target_actor_user_id uuid,
    target_tandem_id uuid, target_memory_id uuid, target_invitation_id uuid,
    notification_payload jsonb, notification_dedupe_key text
) RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, app AS $$
DECLARE result_id uuid;
BEGIN
    IF notification_type NOT IN ('tandem_invitation', 'invitation_accepted', 'memory_added', 'on_this_day', 'member_left', 'member_removed', 'owner_promoted', 'owner_demoted') THEN
        RAISE EXCEPTION 'unsupported notification type';
    END IF;
    IF target_user_id IS NULL OR NOT EXISTS (SELECT 1 FROM public.users WHERE id = target_user_id AND is_active) THEN
        RETURN NULL;
    END IF;
    IF target_actor_user_id IS NOT NULL AND target_actor_user_id <> app.current_user_id() THEN
        RAISE EXCEPTION 'notification actor must be the current user';
    END IF;
    IF target_user_id <> app.current_user_id() AND NOT (
        target_tandem_id IS NOT NULL AND app.is_tandem_member(target_tandem_id, target_user_id)
        OR notification_type = 'tandem_invitation' AND target_invitation_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM public.invitations i JOIN public.users u ON u.id = target_user_id
            WHERE i.id = target_invitation_id AND i.status = 'PENDING' AND lower(i.invited_email) = lower(u.email)
        )
    ) THEN
        RAISE EXCEPTION 'notification recipient is outside the Tandem';
    END IF;
    PERFORM set_config('app.notification_mode', 'true', true);
    INSERT INTO public.notifications (id, user_id, type, actor_user_id, tandem_id, memory_id, invitation_id, payload, dedupe_key)
    VALUES (gen_random_uuid(), target_user_id, notification_type, target_actor_user_id, target_tandem_id,
            target_memory_id, target_invitation_id, COALESCE(notification_payload, '{}'::jsonb), notification_dedupe_key)
    ON CONFLICT (dedupe_key) DO NOTHING RETURNING id INTO result_id;
    RETURN result_id;
END;
$$;

CREATE OR REPLACE FUNCTION app.cancel_user_tandem_notifications(target_user_id uuid, target_tandem_id uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, app AS $$
BEGIN
    PERFORM set_config('app.notification_mode', 'true', true);
    DELETE FROM public.notifications WHERE user_id = target_user_id AND tandem_id = target_tandem_id;
END;
$$;

CREATE OR REPLACE FUNCTION app.clear_user_delivery_state(target_user_id uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, app AS $$
BEGIN
    IF target_user_id <> app.current_user_id() THEN RAISE EXCEPTION 'invalid delivery owner'; END IF;
    PERFORM set_config('app.notification_mode', 'true', true);
    PERFORM set_config('app.worker_mode', 'true', true);
    DELETE FROM public.notifications WHERE user_id = target_user_id;
    DELETE FROM public.notification_outbox WHERE user_id = target_user_id;
    DELETE FROM public.auth_sessions WHERE user_id = target_user_id;
END;
$$;

ALTER TABLE storage_cleanup_failures ENABLE ROW LEVEL SECURITY;
ALTER TABLE storage_cleanup_failures FORCE ROW LEVEL SECURITY;
CREATE POLICY cleanup_worker ON storage_cleanup_failures
    USING (current_setting('app.worker_mode', true) = 'true')
    WITH CHECK (current_setting('app.worker_mode', true) = 'true');
