-- Enable the `citext` extension for case-insensitive text
CREATE EXTENSION IF NOT EXISTS citext;

-- Table for command aliases in different guilds
CREATE TABLE IF NOT EXISTS aliases (
    guild_id BIGINT NOT NULL,
    command_name TEXT NOT NULL,
    alias TEXT NOT NULL,
    PRIMARY KEY(guild_id, alias)
);

CREATE TABLE IF NOT EXISTS warns (
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    reason TEXT NOT NULL,
    date TIMESTAMPTZ NOT NULL
);

-- Table for antispam settings per guild
CREATE TABLE IF NOT EXISTS antispam (
    guild_id BIGINT NOT NULL UNIQUE,
    whitelisted BIGINT[],
    threshold INT NOT NULL DEFAULT 5,
    ladder_threshold INT NOT NULL DEFAULT 10,
    ladder_status BOOLEAN NOT NULL DEFAULT FALSE,
    flood_threshold INT NOT NULL DEFAULT 200,
    flood_status BOOLEAN NOT NULL DEFAULT FALSE,
    status BOOLEAN NOT NULL DEFAULT FALSE,
    timeout INT NOT NULL DEFAULT 300
);

CREATE TABLE IF NOT EXISTS cases (
    guild_id BIGINT NOT NULL,
    case_id BIGINT NOT NULL,
    case_type TEXT NOT NULL,
    message_id BIGINT,
    moderator_id BIGINT NOT NULL,
    target_id BIGINT NOT NULL,
    moderator TEXT,
    target TEXT, 
    reason TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (guild_id, case_id)
);

CREATE TABLE IF NOT EXISTS names (
    user_id bigint NOT NULL,
    type text NOT NULL,
    username text NOT NULL,
    ts timestamp without time zone NOT NULL,
    PRIMARY KEY(user_id, type, username, ts)
);

CREATE TABLE IF NOT EXISTS guild_names (
    guild_id bigint NOT NULL,
    name text NOT NULL,
    ts TIMESTAMP without time zone NOT NULL,
    PRIMARY KEY(guild_id, name, ts)
);

CREATE TABLE IF NOT EXISTS auto_responders (
    guild_id BIGINT NOT NULL,
    trigger TEXT NOT NULL,
    response TEXT NOT NULL,
    strict BOOLEAN DEFAULT FALSE,
    reply BOOLEAN DEFAULT FALSE,
    self_destruct INT DEFAULT NULL,
    ignore_command_checks BOOLEAN DEFAULT FALSE,
    allowed_role_ids BIGINT[] DEFAULT NULL,
    denied_role_ids BIGINT[] DEFAULT NULL,
    allowed_channel_ids BIGINT[] DEFAULT NULL,
    denied_channel_ids BIGINT[] DEFAULT NULL,
    PRIMARY KEY(guild_id, trigger)
);

CREATE TABLE IF NOT EXISTS role_restore (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    roles BIGINT[] NOT NULL,
    PRIMARY KEY(guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS afk (
    user_id BIGINT UNIQUE NOT NULL,
    status TEXT,
    date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auto_reactions (
    guild_id BIGINT NOT NULL,
    trigger TEXT NOT NULL,
    response TEXT[] NOT NULL,
    owner_id BIGINT,
    strict BOOLEAN DEFAULT FALSE,
    PRIMARY KEY(guild_id, trigger, response)
);

-- Table for user reskins
CREATE TABLE IF NOT EXISTS reskin (
    user_id BIGINT NOT NULL UNIQUE,
    username TEXT,
    avatar_url TEXT,
    color INT
);


CREATE TABLE IF NOT EXISTS antiraid (
    guild_id BIGINT NOT NULL UNIQUE,
    raid_status BOOLEAN DEFAULT FALSE,
    status BOOLEAN DEFAULT FALSE,
    raid_triggered_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    raid_expires_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    new_accounts BOOLEAN DEFAULT FALSE,
    new_account_threshold INT DEFAULT 7,
    new_account_punishment INT DEFAULT 1,
    joins BOOLEAN DEFAULT FALSE,
    join_threshold INT DEFAULT NULL,
    join_punishment INT DEFAULT 1,
    no_avatar BOOLEAN DEFAULT FALSE,
    no_avatar_punishment INT DEFAULT 1,
    whitelist BIGINT[] DEFAULT NULL,
    lock_channels BOOLEAN DEFAULT FALSE,
    punish BOOLEAN DEFAULT TRUE
);

-- Configuration table for guilds
CREATE TABLE IF NOT EXISTS config (
    guild_id BIGINT NOT NULL UNIQUE,
    prefix TEXT DEFAULT NULL,
    logs TEXT[] DEFAULT NULL,
    voice_master BIGINT[] DEFAULT NULL,
    transcription BOOLEAN NOT NULL DEFAULT FALSE,
    auto_hex BOOLEAN NOT NULL DEFAULT FALSE,
    reposting BOOLEAN NOT NULL DEFAULT FALSE,
    disabled_commands TEXT[] DEFAULT NULL,
    whitelist BOOLEAN NOT NULL DEFAULT FALSE,
    whitelist_whitelist BIGINT[] DEFAULT NULL,
    whitelist_dm TEXT DEFAULT NULL,
    auto_roles BIGINT[] DEFAULT NULL,
    welcome_message TEXT DEFAULT NULL,
    welcome_channel BIGINT DEFAULT NULL,
    boost_message TEXT DEFAULT NULL,
    boost_channel BIGINT DEFAULT NULL,
    leave_message TEXT DEFAULT NULL,
    leave_channel BIGINT DEFAULT NULL,
    mod_logs BIGINT DEFAULT NULL,
    PRIMARY KEY(guild_id)
);

-- Table for text leveling settings
CREATE TABLE IF NOT EXISTS text_level_settings (
    guild_id BIGINT NOT NULL,
    roles BYTEA DEFAULT NULL,
    award_message TEXT DEFAULT NULL,
    award_message_mode TEXT DEFAULT NULL,
    channel_id BIGINT DEFAULT NULL,
    locked BOOLEAN DEFAULT NULL,
    multiplier FLOAT DEFAULT NULL,
    roles_stack BOOLEAN DEFAULT NULL,
    ignored BYTEA DEFAULT NULL,
    PRIMARY KEY(guild_id)
);

-- Table for tracking user text levels in a guild
CREATE TABLE IF NOT EXISTS text_levels (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    xp BIGINT NOT NULL,
    msgs BIGINT DEFAULT 0,
    messages_enabled BOOLEAN DEFAULT TRUE,
    last_level_up BIGINT DEFAULT 0,
    PRIMARY KEY(guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS message_logs (
    id TEXT NOT NULL UNIQUE,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    messages TEXT NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE
);

-- Table for user configuration settings
CREATE TABLE IF NOT EXISTS user_config (
    user_id BIGINT NOT NULL UNIQUE,
    prefix TEXT,
    username TEXT,
    key TEXT,
    token TEXT,
    birthday TIMESTAMP WITH TIME ZONE,
    timezone TEXT,
    credits INTEGER NOT NULL DEFAULT 0,
    bank INTEGER NOT NULL DEFAULT 0,
    daily TIMESTAMP WITH TIME ZONE,
    monthly TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY(user_id)
);

-- Table for antinuke settings for guilds
CREATE TABLE IF NOT EXISTS antinuke (
    guild_id BIGINT NOT NULL UNIQUE,
    whitelist BIGINT[] NOT NULL DEFAULT '{}',
    admins BIGINT[] NOT NULL DEFAULT '{}',
    botadd JSONB NOT NULL DEFAULT '{}'::JSONB,
    webhook JSONB NOT NULL DEFAULT '{}'::JSONB,
    emoji JSONB NOT NULL DEFAULT '{}'::JSONB,
    ban JSONB NOT NULL DEFAULT '{}'::JSONB,
    kick JSONB NOT NULL DEFAULT '{}'::JSONB,
    channel JSONB NOT NULL DEFAULT '{}'::JSONB,
    role JSONB NOT NULL DEFAULT '{}'::JSONB,
    permissions JSONB[] NOT NULL DEFAULT '{}'::JSONB[],
    PRIMARY KEY(guild_id)
);

CREATE TABLE IF NOT EXISTS lastfm_data (
    user_id BIGINT NOT NULL,
    username TEXT,
    key TEXT,
    token TEXT,
    PRIMARY KEY(user_id)
);


CREATE TABLE IF NOT EXISTS global_ban (
    user_id BIGINT NOT NULL UNIQUE,
    reason TEXT NOT NULL DEFAULT 'No reason provided',
    author BIGINT NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

-- Table for tracking command usage
CREATE TABLE IF NOT EXISTS command_usage (
    name TEXT NOT NULL UNIQUE,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(name)
);

CREATE TABLE IF NOT EXISTS booster_roles (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    PRIMARY KEY(guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS logs (
    guild_id BIGINT NOT NULL,
    log_type TEXT NOT NULL,
    channel_id BIGINT NOT NULL,
    PRIMARY KEY(guild_id, log_type)
);

CREATE TABLE IF NOT EXISTS jail (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    role_ids BIGINT[] NOT NULL,
    PRIMARY KEY(guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS moderation (
    guild_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    jail_id BIGINT NOT NULL,
    category_id BIGINT NOT NULL,
    PRIMARY KEY (guild_id)
);

CREATE TABLE IF NOT EXISTS forcenick (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    nickname TEXT NOT NULL,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS giveaways (
    guild_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    winner_count INT DEFAULT 1,
    prize TEXT,
    hosts BIGINT[] NOT NULL,
    expiration timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    entries BIGINT[],
    win_message_id BIGINT,
    PRIMARY KEY(guild_id, message_id, channel_id)
);

CREATE TABLE IF NOT EXISTS fake_permissions (
    guild_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    permissions TEXT[] NOT NULL,
    PRIMARY KEY(guild_id, role_id)
);

-- Table for recording errors in command usage
CREATE TABLE IF NOT EXISTS traceback (
    command TEXT NOT NULL,
    error_code TEXT NOT NULL,
    error_message TEXT NOT NULL,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    content TEXT NOT NULL,
    date TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY(guild_id, channel_id, user_id, command)
);

CREATE TABLE IF NOT EXISTS trackers (
    guild_id BIGINT NOT NULL,
    tracker_type TEXT NOT NULL,
    channel_ids BIGINT[] NOT NULL,
    PRIMARY KEY(guild_id, tracker_type)
);


CREATE TABLE IF NOT EXISTS invocation (
    guild_id BIGINT NOT NULL,
    command TEXT NOT NULL,
    message_code TEXT,
    dm_code TEXT,
    PRIMARY KEY(guild_id, command)
);

CREATE TABLE IF NOT EXISTS ignored (
    guild_id BIGINT NOT NULL,
    object_id BIGINT NOT NULL,
    object_type TEXT NOT NULL,
    PRIMARY KEY(guild_id, object_id)
);

CREATE TABLE IF NOT EXISTS custom_roles (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    PRIMARY KEY(guild_id, user_id)
);


ALTER TABLE custom_roles OWNER TO postgres;

ALTER TABLE booster_roles OWNER TO postgres;


CREATE TABLE IF NOT EXISTS join_messages (
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    message TEXT NOT NULL,
    self_destruct BIGINT,
    PRIMARY KEY (guild_id, channel_id)
);

CREATE TABLE IF NOT EXISTS leave_messages (
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    message TEXT NOT NULL,
    self_destruct BIGINT,
    PRIMARY KEY (guild_id, channel_id)
);

CREATE TABLE IF NOT EXISTS boost_messages (
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    message TEXT NOT NULL,
    self_destruct BIGINT,
    PRIMARY KEY (guild_id, channel_id)
);

CREATE TABLE IF NOT EXISTS boosters_lost (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expired_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS authorizations (
    guild_id bigint NOT NULL,
    owner_id bigint NOT NULL,
    creator bigint NOT NULL,
    ts timestamp with time zone DEFAULT now() NOT NULL,
    transfers INT NOT NULL DEFAULT 0,
    PRIMARY KEY(guild_id)
);

CREATE TABLE IF NOT EXISTS blacklists (
    object_id BIGINT NOT NULL,
    object_type TEXT NOT NULL,
    creator BIGINT NOT NULL,
    ts timestamp with time zone DEFAULT now() NOT NULL,
    reason TEXT,
    PRIMARY KEY(object_id, object_type)
);

-- Last.fm schema
CREATE SCHEMA IF NOT EXISTS lastfm;

-- Last.fm user configuration table
CREATE TABLE IF NOT EXISTS lastfm.config (
    user_id BIGINT UNIQUE NOT NULL,
    username TEXT NOT NULL,
    score BIGINT DEFAULT 0,
    nowplaying_uses BIGINT DEFAULT 0,
    color BIGINT,
    message TEXT,
    reactions JSONB[] NOT NULL DEFAULT ARRAY[]::JSONB[],
    PRIMARY KEY(user_id)
);

-- Last.fm favorites table
CREATE TABLE IF NOT EXISTS lastfm.favorites (
    user_id BIGINT NOT NULL,
    track TEXT NOT NULL,
    artist TEXT NOT NULL,
    album TEXT NOT NULL,
    PRIMARY KEY(user_id, track, artist, album)
);

-- Last.fm command blacklist table
CREATE TABLE IF NOT EXISTS lastfm.command_blacklist (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    PRIMARY KEY(guild_id, user_id)
);

-- Last.fm commands table
CREATE TABLE IF NOT EXISTS lastfm.commands (
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    public BOOLEAN DEFAULT FALSE,
    command TEXT NOT NULL,
    PRIMARY KEY(user_id, guild_id, command)
);
CREATE TABLE IF NOT EXISTS sticky_message (
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    code TEXT NOT NULL,
    last_message BIGINT,
    PRIMARY KEY(guild_id, channel_id)
);

-- Last.fm locations for tracks and artists
CREATE TABLE IF NOT EXISTS lastfm.locations (
    track CITEXT NOT NULL,
    artist CITEXT NOT NULL,
    youtube TEXT,
    spotify TEXT,
    itunes TEXT,
    PRIMARY KEY(track, artist)
);

-- Last.fm artist plays table
CREATE TABLE IF NOT EXISTS lastfm.artists (
    user_id BIGINT NOT NULL,
    username TEXT NOT NULL,
    artist CITEXT NOT NULL,
    plays BIGINT NOT NULL,
    PRIMARY KEY (user_id, artist)
);

-- Last.fm album plays table
CREATE TABLE IF NOT EXISTS lastfm.albums (
    user_id BIGINT NOT NULL,
    username TEXT NOT NULL,
    artist CITEXT NOT NULL,
    album CITEXT NOT NULL,
    plays BIGINT NOT NULL,
    PRIMARY KEY (user_id, artist, album)
);

-- Last.fm track plays table
CREATE TABLE IF NOT EXISTS lastfm.tracks (
    user_id BIGINT NOT NULL,
    username TEXT NOT NULL,
    artist CITEXT NOT NULL,
    track CITEXT NOT NULL,
    plays BIGINT NOT NULL,
    PRIMARY KEY (user_id, artist, track)
);

-- Last.fm crowns table
CREATE TABLE IF NOT EXISTS lastfm.crowns (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    username TEXT NOT NULL,
    artist CITEXT NOT NULL,
    plays BIGINT NOT NULL,
    PRIMARY KEY(guild_id, artist)
);

-- Last.fm hidden artists table
CREATE TABLE IF NOT EXISTS lastfm.hidden (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    PRIMARY KEY(guild_id, user_id)
);

-- Last.fm artist avatars table
CREATE TABLE IF NOT EXISTS lastfm.artist_avatars (
    artist CITEXT NOT NULL,
    image_url TEXT NOT NULL,
    PRIMARY KEY(artist)
);


CREATE TABLE IF NOT EXISTS avatars (
    user_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    index INT NOT NULL,
    ts TIMESTAMP WITH time zone NOT NULL,
    avatar_hash TEXT NOT NULL,
    url TEXT NOT NULL
);

-- Voicemaster schema
CREATE SCHEMA IF NOT EXISTS voicemaster;

-- Voicemaster guild configuration table
CREATE TABLE IF NOT EXISTS voicemaster.configuration (
    guild_id BIGINT UNIQUE NOT NULL,
    category_id BIGINT NOT NULL,
    interface_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    role_id BIGINT,
    region TEXT,
    bitrate BIGINT,
    PRIMARY KEY(guild_id)
);

-- Voicemaster channels table
CREATE TABLE IF NOT EXISTS voicemaster.channels (
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    owner_id BIGINT NOT NULL,
    PRIMARY KEY(guild_id, channel_id)
);
