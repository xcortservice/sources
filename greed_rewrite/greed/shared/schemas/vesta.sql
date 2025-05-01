CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA public;
COMMENT ON EXTENSION citext IS 'data type for case-insensitive character strings';

--
-- CREATE SCHEMA QUERIES
--

CREATE SCHEMA IF NOT EXISTS "user";
CREATE SCHEMA IF NOT EXISTS guild;
CREATE SCHEMA IF NOT EXISTS timer;
CREATE SCHEMA IF NOT EXISTS level;
CREATE SCHEMA IF NOT EXISTS disboard;

--
-- CREATE TABLE QUERIES
--

CREATE TABLE thread (
    guild_id bigint NOT NULL,
    thread_id bigint NOT NULL
);

CREATE TABLE IF NOT EXISTS aliases (
    guild_id bigint NOT NULL,
    name text NOT NULL,
    invoke text NOT NULL,
    command text NOT NULL
);

CREATE TABLE IF NOT EXISTS antiraid (
    guild_id bigint NOT NULL,
    locked boolean DEFAULT false NOT NULL,
    joins jsonb,
    mentions jsonb,
    avatar jsonb,
    browser jsonb
);

CREATE TABLE IF NOT EXISTS antinuke (
    guild_id bigint NOT NULL,
    whitelist bigint[] DEFAULT '{}'::bigint[] NOT NULL,
    trusted_admins bigint[] DEFAULT '{}'::bigint[] NOT NULL,
    bot boolean DEFAULT false NOT NULL,
    ban jsonb,
    kick jsonb,
    role jsonb,
    channel jsonb,
    webhook jsonb,
    emoji jsonb
);

CREATE TABLE IF NOT EXISTS auto_role (
    guild_id bigint NOT NULL,
    role_id bigint NOT NULL,
    action text NOT NULL,
    delay integer
);

CREATE TABLE IF NOT EXISTS blacklist (
    user_id bigint NOT NULL,
    information text
);

CREATE TABLE IF NOT EXISTS booster_role (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    role_id bigint NOT NULL,
    shared boolean,
    multi_boost_enabled boolean DEFAULT false
);

CREATE TABLE IF NOT EXISTS boosters_lost (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    lasted_for interval NOT NULL,
    ended_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS businesses (
    id integer NOT NULL,
    owner_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    name character varying(100) NOT NULL,
    created_at timestamp without time zone NOT NULL,
    thumbnail_url text,
    funds bigint DEFAULT 0
);

CREATE TABLE IF NOT EXISTS counter (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    option text NOT NULL,
    last_update timestamp with time zone DEFAULT now() NOT NULL,
    rate_limited_until timestamp with time zone
);

CREATE TABLE IF NOT EXISTS donators (
    user_id bigint
);

CREATE TABLE IF NOT EXISTS economy (
    user_id bigint NOT NULL,
    wallet bigint DEFAULT 1000 NOT NULL,
    bank bigint DEFAULT 0 NOT NULL,
    daily timestamp without time zone NOT NULL,
    monthly timestamp without time zone NOT NULL,
    yearly timestamp without time zone NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    daily_streak integer DEFAULT 0,
    monthly_streak integer DEFAULT 0,
    yearly_streak integer DEFAULT 0,
    anonymous boolean DEFAULT false
);

CREATE TABLE IF NOT EXISTS fake_permissions (
    guild_id bigint NOT NULL,
    role_id bigint NOT NULL,
    permission text NOT NULL
);

CREATE TABLE IF NOT EXISTS forcenick (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    nickname character varying(32)
);

CREATE TABLE IF NOT EXISTS gallery (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL
);

CREATE TABLE IF NOT EXISTS gnames (
    guild_id bigint NOT NULL,
    name text NOT NULL,
    changed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS guildblacklist (
    guild_id bigint NOT NULL,
    information text
);

CREATE TABLE IF NOT EXISTS hardban (
    user_id bigint,
    guild_id bigint
);

CREATE TABLE IF NOT EXISTS jobs (
    id integer NOT NULL,
    business_id integer NOT NULL,
    name character varying(50) NOT NULL,
    visibility character varying(7) NOT NULL,
    salary bigint DEFAULT 0,
    guild_id bigint NOT NULL,
    CONSTRAINT jobs_visibility_check CHECK (((visibility)::text = ANY ((ARRAY['public'::character varying, 'private'::character varying])::text[])))
);

CREATE TABLE IF NOT EXISTS ignored_logging (
    guild_id bigint NOT NULL,
    target_id bigint NOT NULL
);

CREATE TABLE IF NOT EXISTS reaction_trigger (
    guild_id bigint NOT NULL,
    trigger citext NOT NULL,
    emoji text NOT NULL
);

CREATE TABLE IF NOT EXISTS response_trigger (
    guild_id bigint NOT NULL,
    trigger citext NOT NULL,
    template text NOT NULL,
    strict boolean DEFAULT false NOT NULL,
    reply boolean DEFAULT false NOT NULL,
    delete boolean DEFAULT false NOT NULL,
    delete_after integer DEFAULT 0 NOT NULL,
    role_id bigint,
    sticker_id bigint
);

CREATE TABLE IF NOT EXISTS counter (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    option text NOT NULL,
    last_update timestamp with time zone DEFAULT now() NOT NULL,
    rate_limited_until timestamp with time zone
);

CREATE TABLE IF NOT EXISTS auto_role (
    guild_id bigint NOT NULL,
    role_id bigint NOT NULL,
    action text NOT NULL,
    delay integer
);

CREATE TABLE IF NOT EXISTS logging (
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    events TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    webhook_id BIGINT,
    PRIMARY KEY (guild_id, channel_id)
);

CREATE TABLE IF NOT EXISTS webhook (
    identifier text NOT NULL,
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    author_id bigint NOT NULL,
    webhook_id bigint NOT NULL
);

CREATE TABLE IF NOT EXISTS starboard (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    self_star boolean DEFAULT true NOT NULL,
    threshold integer DEFAULT 3 NOT NULL,
    emoji text DEFAULT '⭐'::text NOT NULL,
    color integer
);

CREATE TABLE IF NOT EXISTS starboard_entry (
    guild_id bigint NOT NULL,
    star_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    message_id bigint NOT NULL,
    emoji text NOT NULL
);

CREATE TABLE IF NOT EXISTS sticky_message (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    message_id bigint NOT NULL,
    template text NOT NULL
);

CREATE TABLE IF NOT EXISTS ignored_logging (
    guild_id BIGINT NOT NULL,
    target_id BIGINT NOT NULL,
    PRIMARY KEY (guild_id, target_id)
);

CREATE TABLE IF NOT EXISTS booster_role (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    role_id bigint NOT NULL,
    shared boolean,
    multi_boost_enabled boolean DEFAULT false
);

CREATE TABLE IF NOT EXISTS reaction_role (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    message_id bigint NOT NULL,
    role_id bigint NOT NULL,
    emoji text NOT NULL
);

CREATE TABLE IF NOT EXISTS logging (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    events text[] DEFAULT ARRAY[]::text[] NOT NULL,
    webhook_id bigint
);

CREATE TABLE IF NOT EXISTS logging_history (
    id integer NOT NULL,
    guild_id bigint NOT NULL,
    channel_id bigint,
    event_type character varying(50) NOT NULL,
    content jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS name_history (
    user_id bigint NOT NULL,
    username text NOT NULL,
    is_nickname boolean DEFAULT false NOT NULL,
    is_hidden boolean DEFAULT false NOT NULL,
    changed_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS reaction_role (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    message_id bigint NOT NULL,
    role_id bigint NOT NULL,
    emoji text NOT NULL
);

CREATE TABLE IF NOT EXISTS publisher (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL
);


CREATE TABLE IF NOT EXISTS pingonjoin (
    channel_id bigint,
    guild_id bigint
);

CREATE TABLE IF NOT EXISTS reaction_trigger (
    guild_id bigint NOT NULL,
    trigger citext NOT NULL,
    emoji text NOT NULL
);

CREATE TABLE IF NOT EXISTS response_trigger (
    guild_id bigint NOT NULL,
    trigger citext NOT NULL,
    template text NOT NULL,
    strict boolean DEFAULT false NOT NULL,
    reply boolean DEFAULT false NOT NULL,
    delete boolean DEFAULT false NOT NULL,
    delete_after integer DEFAULT 0 NOT NULL,
    role_id bigint
);

CREATE TABLE IF NOT EXISTS roleplay (
    user_id bigint NOT NULL,
    target_id bigint NOT NULL,
    category text NOT NULL,
    amount integer DEFAULT 1 NOT NULL
);

CREATE TABLE IF NOT EXISTS roleplay_enabled (
    enabled boolean,
    guild_id bigint
);

CREATE TABLE IF NOT EXISTS settings (
    guild_id bigint NOT NULL,
    prefixes text[] DEFAULT '{}'::text[] NOT NULL,
    prefix VARCHAR(7),
    reskin boolean DEFAULT false NOT NULL,
    reposter_prefix boolean DEFAULT true NOT NULL,
    reposter_delete boolean DEFAULT false NOT NULL,
    reposter_embed boolean DEFAULT true NOT NULL,
    transcription boolean DEFAULT false NOT NULL,
    welcome_removal boolean DEFAULT false NOT NULL,
    booster_role_base_id bigint,
    booster_role_include_ids bigint[] DEFAULT '{}'::bigint[] NOT NULL,
    lock_role_id bigint,
    lock_ignore_ids bigint[] DEFAULT '{}'::bigint[] NOT NULL,
    log_ignore_ids bigint[] DEFAULT '{}'::bigint[] NOT NULL,
    reassign_ignore_ids bigint[] DEFAULT '{}'::bigint[] NOT NULL,
    reassign_roles boolean DEFAULT false NOT NULL,
    invoke_kick text,
    invoke_ban text,
    invoke_unban text,
    invoke_timeout text,
    invoke_untimeout text,
    invoke_play text,
    dm_enabled boolean DEFAULT true NOT NULL,
    dm_ban text,
    dm_unban text,
    dm_kick text,
    dm_jail text,
    dm_unjail text,
    dm_mute text,
    dm_unmute text,
    dm_warn text,
    dm_timeout text,
    dm_untimeout text,
    dm_role_add text,
    dm_role_remove text,
    dm_antinuke_ban text,
    dm_antinuke_kick text,
    dm_antinuke_strip text,
    dm_antiraid_ban text,
    dm_antiraid_kick text,
    dm_antiraid_timeout text,
    dm_antiraid_strip text
    play_panel boolean DEFAULT true NOT NULL,
    play_deletion boolean DEFAULT false NOT NULL,
    safesearch_level text DEFAULT 'strict'::text NOT NULL,
    author text
);

CREATE TABLE IF NOT EXISTS tags (
    guild_id bigint NOT NULL,
    name text NOT NULL,
    owner_id bigint,
    template text,
    uses bigint DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    restricted_user bigint,
    restricted_role bigint
);

CREATE TABLE IF NOT EXISTS shutup (
    guild_id bigint,
    user_id bigint
);

CREATE TABLE IF NOT EXISTS tag_aliases (
    guild_id bigint NOT NULL,
    alias text NOT NULL,
    original text
);


CREATE SCHEMA IF NOT EXISTS lastfm;

CREATE TABLE IF NOT EXISTS lastfm.config (
    user_id bigint NOT NULL,
    username public.citext NOT NULL,
    color bigint,
    command text,
    reactions text[] DEFAULT '{}'::text[] NOT NULL,
    embed_mode text DEFAULT 'default'::text NOT NULL,
    last_indexed timestamp with time zone DEFAULT now() NOT NULL,
    access_token text,
    web_authentication boolean DEFAULT false
);


CREATE TABLE IF NOT EXISTS lastfm.crowns (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    artist public.citext NOT NULL,
    claimed_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS lastfm.hidden (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL
);

CREATE TABLE IF NOT EXISTS lastfm.tracks (
    user_id bigint NOT NULL,
    username text NOT NULL,
    artist public.citext NOT NULL,
    track public.citext NOT NULL,
    plays bigint NOT NULL
);

CREATE TABLE IF NOT EXISTS level.config (
    guild_id bigint NOT NULL,
    status boolean DEFAULT true NOT NULL,
    cooldown integer DEFAULT 60 NOT NULL,
    max_level integer DEFAULT 0 NOT NULL,
    stack_roles boolean DEFAULT true NOT NULL,
    formula_multiplier double precision DEFAULT 1 NOT NULL,
    xp_multiplier double precision DEFAULT 1 NOT NULL,
    xp_min integer DEFAULT 15 NOT NULL,
    xp_max integer DEFAULT 40 NOT NULL,
    effort_status boolean DEFAULT false NOT NULL,
    effort_text bigint DEFAULT 25 NOT NULL,
    effort_image bigint DEFAULT 3 NOT NULL,
    effort_booster bigint DEFAULT 10 NOT NULL
);



CREATE TABLE IF NOT EXISTS uwulock (
    guild_id bigint,
    user_id bigint
);

CREATE TABLE IF NOT EXISTS voicemaster (
    guild_id bigint,
    voice_id bigint,
    text_id bigint,
    category_id bigint
);

CREATE TABLE IF NOT EXISTS whitelist (
    id integer NOT NULL,
    guild_id bigint NOT NULL,
    user_id bigint,
    status boolean DEFAULT false NOT NULL,
    action text DEFAULT 'kick'::text NOT NULL
);

--
-- DISBOARD TABLE QUERIES
--

CREATE TABLE IF NOT EXISTS disboard.bump (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    bumped_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS disboard.config (
    guild_id bigint NOT NULL,
    status boolean DEFAULT true NOT NULL,
    channel_id bigint,
    last_channel_id bigint,
    last_user_id bigint,
    message text,
    thank_message text,
    next_bump timestamp with time zone
);

--
-- USER TABLE QUERIES
--

CREATE TABLE IF NOT EXISTS "user".settings (
    user_id BIGINT PRIMARY KEY NOT NULL,
    config JSONB DEFAULT '{}',
    prefix VARCHAR(7)
);

CREATE TABLE IF NOT EXISTS "user".oauth_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_type TEXT NOT NULL,
    scope TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS "user".api_sessions (
    token TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_used_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_agent TEXT,
    ip_address INET
);

CREATE TABLE IF NOT EXISTS guild.settings (
    guild_id BIGINT PRIMARY KEY NOT NULL,
    config JSONB DEFAULT '{}'
);

--
-- TIMER TABLE QUERIES
--

CREATE TABLE IF NOT EXISTS timer.message (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    template text NOT NULL,
    "interval" integer NOT NULL,
    next_trigger timestamp with time zone NOT NULL
);

CREATE TABLE IF NOT EXISTS timer.purge (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    "interval" integer NOT NULL,
    next_trigger timestamp with time zone NOT NULL,
    method text DEFAULT 'bulk'::text NOT NULL
);

--
-- LEVEL TABLE QUERIES
--

CREATE TABLE IF NOT EXISTS level.config (
    guild_id bigint NOT NULL,
    status boolean DEFAULT true NOT NULL,
    cooldown integer DEFAULT 60 NOT NULL,
    max_level integer DEFAULT 0 NOT NULL,
    stack_roles boolean DEFAULT true NOT NULL,
    formula_multiplier double precision DEFAULT 1 NOT NULL,
    xp_multiplier double precision DEFAULT 1 NOT NULL,
    xp_min integer DEFAULT 15 NOT NULL,
    xp_max integer DEFAULT 40 NOT NULL,
    effort_status boolean DEFAULT false NOT NULL,
    effort_text bigint DEFAULT 25 NOT NULL,
    effort_image bigint DEFAULT 3 NOT NULL,
    effort_booster bigint DEFAULT 10 NOT NULL
);

CREATE TABLE IF NOT EXISTS level.member (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    xp integer DEFAULT 0 NOT NULL,
    level integer DEFAULT 0 NOT NULL,
    total_xp integer DEFAULT 0 NOT NULL,
    last_message timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS level.notification (
    guild_id bigint NOT NULL,
    channel_id bigint,
    dm boolean DEFAULT false NOT NULL,
    template text
);

CREATE TABLE IF NOT EXISTS level.role (
    guild_id bigint NOT NULL,
    role_id bigint NOT NULL,
    level integer NOT NULL
);

CREATE TABLE IF NOT EXISTS workers (
    user_id bigint NOT NULL,
    job_id integer NOT NULL,
    last_worked timestamp without time zone,
    guild_id bigint NOT NULL
);

CREATE TABLE IF NOT EXISTS pagination (
    guild_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    creator_id BIGINT NOT NULL,
    pages TEXT[] NOT NULL,
    current_page BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY(guild_id, message_id, channel_id)
);



--
-- ALTER TABLE QUERIES
--

ALTER TABLE ONLY logging_history ALTER COLUMN id SET DEFAULT nextval('logging_history_id_seq'::regclass);
ALTER TABLE ONLY jobs ALTER COLUMN id SET DEFAULT nextval('jobs_id_seq'::regclass);
ALTER TABLE ONLY whitelist ALTER COLUMN id SET DEFAULT nextval('whitelist_id_seq'::regclass);
ALTER TABLE ONLY businesses ALTER COLUMN id SET DEFAULT nextval('businesses_id_seq'::regclass);

ALTER TABLE ONLY thread
    ADD CONSTRAINT thread_pkey PRIMARY KEY (guild_id, thread_id);

ALTER TABLE ONLY forcenick
    ADD CONSTRAINT forcenick_pkey PRIMARY KEY (guild_id, user_id);

ALTER TABLE ONLY webhook
    ADD CONSTRAINT webhook_pkey PRIMARY KEY (channel_id, webhook_id);

ALTER TABLE ONLY booster_role
    ADD CONSTRAINT booster_role_pkey PRIMARY KEY (guild_id, user_id);

ALTER TABLE ONLY auto_role
    ADD CONSTRAINT auto_role_pkey PRIMARY KEY (guild_id, role_id, action);

ALTER TABLE ONLY starboard
    ADD CONSTRAINT starboard_pkey PRIMARY KEY (guild_id, emoji);

ALTER TABLE ONLY starboard_entry
    ADD CONSTRAINT starboard_entry_pkey PRIMARY KEY (guild_id, channel_id, message_id, emoji);

ALTER TABLE ONLY starboard_entry
    ADD CONSTRAINT starboard_entry_guild_id_emoji_fkey FOREIGN KEY (guild_id, emoji) REFERENCES starboard(guild_id, emoji) ON DELETE CASCADE;

ALTER TABLE ONLY sticky_message
    ADD CONSTRAINT sticky_message_pkey PRIMARY KEY (guild_id, channel_id);

ALTER TABLE ONLY response_trigger
    ADD CONSTRAINT response_trigger_pkey PRIMARY KEY (guild_id, trigger);

ALTER TABLE ONLY reaction_trigger
    ADD CONSTRAINT reaction_trigger_pkey PRIMARY KEY (guild_id, trigger, emoji);

ALTER TABLE ONLY counter
    ADD CONSTRAINT counter_pkey PRIMARY KEY (guild_id, channel_id);

ALTER TABLE logging
    ADD COLUMN webhook_id BIGINT,
    ALTER COLUMN events TYPE TEXT[] USING ARRAY[events]::TEXT[],
    ALTER COLUMN events SET DEFAULT ARRAY[]::TEXT[];

--
-- ALTER SEQUENCE QUERIES
--

ALTER SEQUENCE whitelist_id_seq OWNED BY whitelist.id;

--
-- TIMER ALTER TABLE QUERIES
--

ALTER TABLE ONLY timer.message
    ADD CONSTRAINT message_pkey PRIMARY KEY (guild_id, channel_id);

ALTER TABLE ONLY timer.purge
    ADD CONSTRAINT purge_pkey PRIMARY KEY (guild_id, channel_id);

--
-- LEVEL ALTER TABLE QUERIES
--

ALTER TABLE ONLY level.config
    ADD CONSTRAINT config_guild_id_key UNIQUE (guild_id);

ALTER TABLE ONLY level.member
    ADD CONSTRAINT member_pkey PRIMARY KEY (guild_id, user_id);

ALTER TABLE ONLY level.notification
    ADD CONSTRAINT notification_pkey PRIMARY KEY (guild_id);

ALTER TABLE ONLY level.role
    ADD CONSTRAINT role_pkey PRIMARY KEY (guild_id, level);

ALTER TABLE ONLY level.role
    ADD CONSTRAINT role_role_id_key UNIQUE (role_id);

ALTER TABLE ONLY level.config
    ADD CONSTRAINT config_guild_id_fkey FOREIGN KEY (guild_id) REFERENCES settings(guild_id) ON DELETE CASCADE;

ALTER TABLE ONLY level.member
    ADD CONSTRAINT member_guild_id_fkey FOREIGN KEY (guild_id) REFERENCES level.config(guild_id) ON DELETE CASCADE;

ALTER TABLE ONLY level.notification
    ADD CONSTRAINT notification_guild_id_fkey FOREIGN KEY (guild_id) REFERENCES level.config(guild_id) ON DELETE CASCADE;

ALTER TABLE ONLY level.role
    ADD CONSTRAINT role_guild_id_fkey FOREIGN KEY (guild_id) REFERENCES level.config(guild_id) ON DELETE CASCADE;

--
-- CREATE SEQUENCE QUERIES
--

CREATE SEQUENCE IF NOT EXISTS businesses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE SEQUENCE IF NOT EXISTS jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE SEQUENCE IF NOT EXISTS logging_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE SEQUENCE IF NOT EXISTS whitelist_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;




