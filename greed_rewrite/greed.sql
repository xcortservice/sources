--
-- PostgreSQL database dump
--

-- Dumped from database version 14.17 (Ubuntu 14.17-0ubuntu0.22.04.1)
-- Dumped by pg_dump version 14.17 (Ubuntu 14.17-0ubuntu0.22.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'SQL_ASCII';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: antiinvite; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA antiinvite;


ALTER SCHEMA antiinvite OWNER TO postgres;

--
-- Name: antilink; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA antilink;


ALTER SCHEMA antilink OWNER TO postgres;

--
-- Name: automod; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA automod;


ALTER SCHEMA automod OWNER TO postgres;

--
-- Name: autoreact; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA autoreact;


ALTER SCHEMA autoreact OWNER TO postgres;

--
-- Name: autoresponder; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA autoresponder;


ALTER SCHEMA autoresponder OWNER TO postgres;

--
-- Name: commands; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA commands;


ALTER SCHEMA commands OWNER TO postgres;

--
-- Name: confess; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA confess;


ALTER SCHEMA confess OWNER TO postgres;

--
-- Name: dm_messages; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA dm_messages;


ALTER SCHEMA dm_messages OWNER TO postgres;

--
-- Name: forcenick; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA forcenick;


ALTER SCHEMA forcenick OWNER TO postgres;

--
-- Name: guild; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA guild;


ALTER SCHEMA guild OWNER TO postgres;

--
-- Name: imageonly; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA imageonly;


ALTER SCHEMA imageonly OWNER TO postgres;

--
-- Name: invoke; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA invoke;


ALTER SCHEMA invoke OWNER TO postgres;

--
-- Name: lastfm; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA lastfm;


ALTER SCHEMA lastfm OWNER TO postgres;

--
-- Name: lastfm_library; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA lastfm_library;


ALTER SCHEMA lastfm_library OWNER TO postgres;

--
-- Name: levels; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA levels;


ALTER SCHEMA levels OWNER TO postgres;

--
-- Name: metrics; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA metrics;


ALTER SCHEMA metrics OWNER TO postgres;

--
-- Name: reaction_roles; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA reaction_roles;


ALTER SCHEMA reaction_roles OWNER TO postgres;

--
-- Name: reskin; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA reskin;


ALTER SCHEMA reskin OWNER TO postgres;

--
-- Name: starboard; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA starboard;


ALTER SCHEMA starboard OWNER TO postgres;

--
-- Name: status; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA status;


ALTER SCHEMA status OWNER TO postgres;

--
-- Name: twitch; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA twitch;


ALTER SCHEMA twitch OWNER TO postgres;

--
-- Name: uwulock; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA uwulock;


ALTER SCHEMA uwulock OWNER TO postgres;

--
-- Name: wordfilter; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA wordfilter;


ALTER SCHEMA wordfilter OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: main; Type: TABLE; Schema: antiinvite; Owner: postgres
--

CREATE TABLE antiinvite.main (
    guild_id bigint,
    channel_id bigint
);


ALTER TABLE antiinvite.main OWNER TO postgres;

--
-- Name: roles; Type: TABLE; Schema: antiinvite; Owner: postgres
--

CREATE TABLE antiinvite.roles (
    guild_id bigint,
    role_id bigint
);


ALTER TABLE antiinvite.roles OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: antiinvite; Owner: postgres
--

CREATE TABLE antiinvite.users (
    guild_id bigint,
    user_id bigint
);


ALTER TABLE antiinvite.users OWNER TO postgres;

--
-- Name: main; Type: TABLE; Schema: antilink; Owner: postgres
--

CREATE TABLE antilink.main (
    guild_id bigint,
    channel_id bigint
);


ALTER TABLE antilink.main OWNER TO postgres;

--
-- Name: roles; Type: TABLE; Schema: antilink; Owner: postgres
--

CREATE TABLE antilink.roles (
    guild_id bigint,
    role_id bigint
);


ALTER TABLE antilink.roles OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: antilink; Owner: postgres
--

CREATE TABLE antilink.users (
    guild_id bigint,
    user_id bigint
);


ALTER TABLE antilink.users OWNER TO postgres;

--
-- Name: filter; Type: TABLE; Schema: automod; Owner: postgres
--

CREATE TABLE automod.filter (
    guild_id bigint,
    word text
);


ALTER TABLE automod.filter OWNER TO postgres;

--
-- Name: spam; Type: TABLE; Schema: automod; Owner: postgres
--

CREATE TABLE automod.spam (
    guild_id bigint NOT NULL,
    status boolean,
    difference integer,
    threshold integer,
    punishment text
);


ALTER TABLE automod.spam OWNER TO postgres;

--
-- Name: channels; Type: TABLE; Schema: autoreact; Owner: postgres
--

CREATE TABLE autoreact.channels (
    channel_id bigint,
    trigger text,
    guild_id bigint
);


ALTER TABLE autoreact.channels OWNER TO postgres;

--
-- Name: roles; Type: TABLE; Schema: autoreact; Owner: postgres
--

CREATE TABLE autoreact.roles (
    role_id bigint,
    trigger text,
    guild_id bigint
);


ALTER TABLE autoreact.roles OWNER TO postgres;

--
-- Name: channels; Type: TABLE; Schema: autoresponder; Owner: postgres
--

CREATE TABLE autoresponder.channels (
    channel_id bigint,
    trigger text,
    guild_id bigint
);


ALTER TABLE autoresponder.channels OWNER TO postgres;

--
-- Name: roles; Type: TABLE; Schema: autoresponder; Owner: postgres
--

CREATE TABLE autoresponder.roles (
    role_id bigint,
    trigger text,
    guild_id bigint
);


ALTER TABLE autoresponder.roles OWNER TO postgres;

--
-- Name: disabled; Type: TABLE; Schema: commands; Owner: postgres
--

CREATE TABLE commands.disabled (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    command text NOT NULL
);


ALTER TABLE commands.disabled OWNER TO postgres;

--
-- Name: roles; Type: TABLE; Schema: commands; Owner: postgres
--

CREATE TABLE commands.roles (
    guild_id bigint,
    role_id bigint,
    command text
);


ALTER TABLE commands.roles OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: commands; Owner: postgres
--

CREATE TABLE commands.users (
    guild_id bigint,
    user_id bigint,
    command text
);


ALTER TABLE commands.users OWNER TO postgres;

--
-- Name: roles; Type: TABLE; Schema: confess; Owner: postgres
--

CREATE TABLE confess.roles (
    role_id bigint,
    guild_id bigint
);


ALTER TABLE confess.roles OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: confess; Owner: postgres
--

CREATE TABLE confess.users (
    user_id bigint,
    guild_id bigint
);


ALTER TABLE confess.users OWNER TO postgres;

--
-- Name: ban; Type: TABLE; Schema: dm_messages; Owner: postgres
--

CREATE TABLE dm_messages.ban (
    guild_id bigint NOT NULL,
    message text
);


ALTER TABLE dm_messages.ban OWNER TO postgres;

--
-- Name: kick; Type: TABLE; Schema: dm_messages; Owner: postgres
--

CREATE TABLE dm_messages.kick (
    guild_id bigint NOT NULL,
    message text
);


ALTER TABLE dm_messages.kick OWNER TO postgres;

--
-- Name: mute; Type: TABLE; Schema: dm_messages; Owner: postgres
--

CREATE TABLE dm_messages.mute (
    guild_id bigint NOT NULL,
    message text
);


ALTER TABLE dm_messages.mute OWNER TO postgres;

--
-- Name: warn; Type: TABLE; Schema: dm_messages; Owner: postgres
--

CREATE TABLE dm_messages.warn (
    guild_id bigint NOT NULL,
    message text
);


ALTER TABLE dm_messages.warn OWNER TO postgres;

--
-- Name: roles; Type: TABLE; Schema: forcenick; Owner: postgres
--

CREATE TABLE forcenick.roles (
    role_id bigint,
    guild_id bigint
);


ALTER TABLE forcenick.roles OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: forcenick; Owner: postgres
--

CREATE TABLE forcenick.users (
    user_id bigint,
    guild_id bigint
);


ALTER TABLE forcenick.users OWNER TO postgres;

--
-- Name: boost; Type: TABLE; Schema: guild; Owner: postgres
--

CREATE TABLE guild.boost (
    guild_id bigint,
    channel_id bigint,
    message text
);


ALTER TABLE guild.boost OWNER TO postgres;

--
-- Name: main; Type: TABLE; Schema: imageonly; Owner: postgres
--

CREATE TABLE imageonly.main (
    guild_id bigint,
    channel_id bigint
);


ALTER TABLE imageonly.main OWNER TO postgres;

--
-- Name: roles; Type: TABLE; Schema: imageonly; Owner: postgres
--

CREATE TABLE imageonly.roles (
    guild_id bigint,
    role_id bigint
);


ALTER TABLE imageonly.roles OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: imageonly; Owner: postgres
--

CREATE TABLE imageonly.users (
    guild_id bigint,
    user_id bigint
);


ALTER TABLE imageonly.users OWNER TO postgres;

--
-- Name: ban; Type: TABLE; Schema: invoke; Owner: postgres
--

CREATE TABLE invoke.ban (
    guild_id bigint NOT NULL,
    message text
);


ALTER TABLE invoke.ban OWNER TO postgres;

--
-- Name: kick; Type: TABLE; Schema: invoke; Owner: postgres
--

CREATE TABLE invoke.kick (
    guild_id bigint NOT NULL,
    message text
);


ALTER TABLE invoke.kick OWNER TO postgres;

--
-- Name: mute; Type: TABLE; Schema: invoke; Owner: postgres
--

CREATE TABLE invoke.mute (
    guild_id bigint NOT NULL,
    message text
);


ALTER TABLE invoke.mute OWNER TO postgres;

--
-- Name: warn; Type: TABLE; Schema: invoke; Owner: postgres
--

CREATE TABLE invoke.warn (
    guild_id bigint NOT NULL,
    message text
);


ALTER TABLE invoke.warn OWNER TO postgres;

--
-- Name: ce; Type: TABLE; Schema: lastfm; Owner: postgres
--

CREATE TABLE lastfm.ce (
    user_id bigint NOT NULL,
    msg text
);


ALTER TABLE lastfm.ce OWNER TO postgres;

--
-- Name: command; Type: TABLE; Schema: lastfm; Owner: postgres
--

CREATE TABLE lastfm.command (
    user_id bigint NOT NULL,
    command text
);


ALTER TABLE lastfm.command OWNER TO postgres;

--
-- Name: conf; Type: TABLE; Schema: lastfm; Owner: postgres
--

CREATE TABLE lastfm.conf (
    user_id bigint NOT NULL,
    username text,
    up text,
    down text,
    session_key text
);


ALTER TABLE lastfm.conf OWNER TO postgres;

--
-- Name: lastfm_likes; Type: TABLE; Schema: lastfm; Owner: postgres
--

CREATE TABLE lastfm.lastfm_likes (
    user_id bigint NOT NULL,
    track character varying(255) NOT NULL,
    artist character varying(255) NOT NULL
);


ALTER TABLE lastfm.lastfm_likes OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: lastfm; Owner: postgres
--

CREATE TABLE lastfm.users (
    user_id bigint NOT NULL,
    username text,
    artists jsonb,
    tracks jsonb,
    albums text
);


ALTER TABLE lastfm.users OWNER TO postgres;

--
-- Name: albums; Type: TABLE; Schema: lastfm_library; Owner: postgres
--

CREATE TABLE lastfm_library.albums (
    user_id bigint NOT NULL,
    username text NOT NULL,
    artist text NOT NULL,
    album text NOT NULL,
    plays bigint NOT NULL
);


ALTER TABLE lastfm_library.albums OWNER TO postgres;

--
-- Name: artists; Type: TABLE; Schema: lastfm_library; Owner: postgres
--

CREATE TABLE lastfm_library.artists (
    user_id bigint NOT NULL,
    username text NOT NULL,
    artist text NOT NULL,
    plays bigint NOT NULL
);


ALTER TABLE lastfm_library.artists OWNER TO postgres;

--
-- Name: tracks; Type: TABLE; Schema: lastfm_library; Owner: postgres
--

CREATE TABLE lastfm_library.tracks (
    user_id bigint NOT NULL,
    username text NOT NULL,
    artist text NOT NULL,
    track text NOT NULL,
    plays bigint NOT NULL
);


ALTER TABLE lastfm_library.tracks OWNER TO postgres;

--
-- Name: channels; Type: TABLE; Schema: levels; Owner: postgres
--

CREATE TABLE levels.channels (
    channel_id bigint,
    guild_id bigint
);


ALTER TABLE levels.channels OWNER TO postgres;

--
-- Name: main; Type: TABLE; Schema: levels; Owner: postgres
--

CREATE TABLE levels.main (
    guild_id bigint NOT NULL,
    dm boolean DEFAULT false,
    dm_message text,
    message text,
    enabled boolean DEFAULT false
);


ALTER TABLE levels.main OWNER TO postgres;

--
-- Name: metrics; Type: TABLE; Schema: levels; Owner: postgres
--

CREATE TABLE levels.metrics (
    guild_id bigint,
    user_id bigint NOT NULL,
    level integer DEFAULT 1,
    exp bigint DEFAULT 1,
    threshold bigint DEFAULT 100
);


ALTER TABLE levels.metrics OWNER TO postgres;

--
-- Name: rewards; Type: TABLE; Schema: levels; Owner: postgres
--

CREATE TABLE levels.rewards (
    guild_id bigint,
    role_id bigint,
    level integer
);


ALTER TABLE levels.rewards OWNER TO postgres;

--
-- Name: roles; Type: TABLE; Schema: levels; Owner: postgres
--

CREATE TABLE levels.roles (
    role_id bigint,
    guild_id bigint
);


ALTER TABLE levels.roles OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: levels; Owner: postgres
--

CREATE TABLE levels.users (
    user_id bigint,
    guild_id bigint
);


ALTER TABLE levels.users OWNER TO postgres;

--
-- Name: avatars; Type: TABLE; Schema: metrics; Owner: postgres
--

CREATE TABLE metrics.avatars (
    user_id bigint,
    avatar text,
    "timestamp" timestamp with time zone NOT NULL
);


ALTER TABLE metrics.avatars OWNER TO postgres;

--
-- Name: banners; Type: TABLE; Schema: metrics; Owner: postgres
--

CREATE TABLE metrics.banners (
    user_id bigint,
    banner text
);


ALTER TABLE metrics.banners OWNER TO postgres;

--
-- Name: names; Type: TABLE; Schema: metrics; Owner: postgres
--

CREATE TABLE metrics.names (
    user_id bigint,
    name text,
    "timestamp" bigint
);


ALTER TABLE metrics.names OWNER TO postgres;

--
-- Name: achievements; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.achievements (
    user_id bigint NOT NULL,
    achievement text[]
);


ALTER TABLE public.achievements OWNER TO postgres;

--
-- Name: activity_cache; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.activity_cache (
    user_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    text_messages integer DEFAULT 0,
    voice_minutes integer DEFAULT 0,
    last_update timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.activity_cache OWNER TO postgres;

--
-- Name: activity_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.activity_log (
    log_id integer NOT NULL,
    user_id bigint,
    guild_id bigint,
    activity_type character varying(10),
    xp_gained integer,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.activity_log OWNER TO postgres;

--
-- Name: activity_log_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.activity_log_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.activity_log_log_id_seq OWNER TO postgres;

--
-- Name: activity_log_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.activity_log_log_id_seq OWNED BY public.activity_log.log_id;


--
-- Name: admins_deathinstance; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.admins_deathinstance (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL
);


ALTER TABLE public.admins_deathinstance OWNER TO postgres;

--
-- Name: afk; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.afk (
    user_id bigint NOT NULL,
    status text,
    date timestamp without time zone
);


ALTER TABLE public.afk OWNER TO postgres;

--
-- Name: ai_setup; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ai_setup (
    guild_id text NOT NULL
);


ALTER TABLE public.ai_setup OWNER TO postgres;

--
-- Name: aliases; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.aliases (
    guild_id bigint NOT NULL,
    command_name character varying(255) NOT NULL,
    alias character varying(255)
);


ALTER TABLE public.aliases OWNER TO postgres;

--
-- Name: antinuke; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.antinuke (
    guild_id bigint NOT NULL,
    bot_add boolean DEFAULT false,
    guild_update boolean DEFAULT false,
    channel_update boolean DEFAULT false,
    role_update boolean DEFAULT false,
    kick boolean DEFAULT false,
    ban boolean DEFAULT false,
    webhooks boolean DEFAULT false,
    member_prune boolean DEFAULT false,
    threshold integer DEFAULT 0,
    punishment character varying(50) DEFAULT NULL::character varying,
    log_channel bigint
);


ALTER TABLE public.antinuke OWNER TO postgres;

--
-- Name: antinuke_admin; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.antinuke_admin (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL
);


ALTER TABLE public.antinuke_admin OWNER TO postgres;

--
-- Name: antinuke_threshold; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.antinuke_threshold (
    guild_id bigint NOT NULL,
    bot_add bigint DEFAULT 0,
    role_update bigint DEFAULT 0,
    channel_update bigint DEFAULT 0,
    guild_update bigint DEFAULT 0,
    kick bigint DEFAULT 0,
    ban bigint DEFAULT 0,
    member_prune bigint DEFAULT 0,
    webhooks bigint DEFAULT 0
);


ALTER TABLE public.antinuke_threshold OWNER TO postgres;

--
-- Name: antinuke_whitelist; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.antinuke_whitelist (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL
);


ALTER TABLE public.antinuke_whitelist OWNER TO postgres;

--
-- Name: antiraid; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.antiraid (
    guild_id bigint NOT NULL,
    defaultpfp boolean DEFAULT false,
    punishment text DEFAULT 'ban'::text
);


ALTER TABLE public.antiraid OWNER TO postgres;

--
-- Name: antisr_guilds; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.antisr_guilds (
    guild_id bigint NOT NULL
);


ALTER TABLE public.antisr_guilds OWNER TO postgres;

--
-- Name: antisr_ignores; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.antisr_ignores (
    guild_id bigint NOT NULL,
    target_id bigint NOT NULL,
    is_role boolean
);


ALTER TABLE public.antisr_ignores OWNER TO postgres;

--
-- Name: antisr_users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.antisr_users (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL
);


ALTER TABLE public.antisr_users OWNER TO postgres;

--
-- Name: auth; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.auth (
    guild_id bigint NOT NULL,
    ts timestamp without time zone NOT NULL
);


ALTER TABLE public.auth OWNER TO postgres;

--
-- Name: authorized; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.authorized (
    guild_id bigint,
    user_id bigint
);


ALTER TABLE public.authorized OWNER TO postgres;

--
-- Name: auto_reactions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.auto_reactions (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    emojis text[]
);


ALTER TABLE public.auto_reactions OWNER TO postgres;

--
-- Name: auto_responses; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.auto_responses (
    guild_id bigint NOT NULL,
    trigger text NOT NULL,
    response text NOT NULL,
    strict boolean DEFAULT false,
    role_id bigint,
    channel_id bigint
);


ALTER TABLE public.auto_responses OWNER TO postgres;

--
-- Name: auto_roles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.auto_roles (
    guild_id bigint NOT NULL,
    role_id bigint NOT NULL,
    humans boolean DEFAULT false,
    bots boolean DEFAULT false
);


ALTER TABLE public.auto_roles OWNER TO postgres;

--
-- Name: auto_transcribe; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.auto_transcribe (
    guild_id bigint NOT NULL
);


ALTER TABLE public.auto_transcribe OWNER TO postgres;

--
-- Name: autobanner_channels; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.autobanner_channels (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL
);


ALTER TABLE public.autobanner_channels OWNER TO postgres;

--
-- Name: automod; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.automod (
    guild_id bigint NOT NULL,
    rule_name text,
    rule_type text,
    rule_data text
);


ALTER TABLE public.automod OWNER TO postgres;

--
-- Name: automod_timeout; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.automod_timeout (
    guild_id bigint NOT NULL,
    timeframe text NOT NULL
);


ALTER TABLE public.automod_timeout OWNER TO postgres;

--
-- Name: autoname_channels; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.autoname_channels (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL
);


ALTER TABLE public.autoname_channels OWNER TO postgres;

--
-- Name: autopfp; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.autopfp (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    categories text[] NOT NULL
);


ALTER TABLE public.autopfp OWNER TO postgres;

--
-- Name: autopfp_channels; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.autopfp_channels (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL
);


ALTER TABLE public.autopfp_channels OWNER TO postgres;

--
-- Name: autoreact; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.autoreact (
    guild_id bigint NOT NULL,
    keyword character varying(32) NOT NULL,
    reaction character varying(128) NOT NULL
);


ALTER TABLE public.autoreact OWNER TO postgres;

--
-- Name: autoreact_event; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.autoreact_event (
    guild_id bigint NOT NULL,
    event character varying(32) NOT NULL,
    reaction character varying(128) NOT NULL
);


ALTER TABLE public.autoreact_event OWNER TO postgres;

--
-- Name: autoresponder; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.autoresponder (
    guild_id bigint NOT NULL,
    trig text NOT NULL,
    response text NOT NULL,
    strict boolean DEFAULT false,
    reply boolean DEFAULT false
);


ALTER TABLE public.autoresponder OWNER TO postgres;

--
-- Name: autorole; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.autorole (
    guild_id bigint,
    role_id bigint
);


ALTER TABLE public.autorole OWNER TO postgres;

--
-- Name: autovanity_channels; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.autovanity_channels (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL
);


ALTER TABLE public.autovanity_channels OWNER TO postgres;

--
-- Name: avatars; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.avatars (
    user_id bigint,
    content_type text,
    avatar bytea,
    id text,
    ts timestamp without time zone DEFAULT now()
);


ALTER TABLE public.avatars OWNER TO postgres;

--
-- Name: birthday; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.birthday (
    user_id bigint NOT NULL,
    ts timestamp with time zone NOT NULL
);


ALTER TABLE public.birthday OWNER TO postgres;

--
-- Name: birthdays; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.birthdays (
    user_id bigint NOT NULL,
    birthday character varying(64)
);


ALTER TABLE public.birthdays OWNER TO postgres;

--
-- Name: blacklist; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.blacklist (
    user_id bigint NOT NULL,
    note text NOT NULL,
    blacklist_author bigint
);


ALTER TABLE public.blacklist OWNER TO postgres;

--
-- Name: blacklisted; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.blacklisted (
    object_id bigint NOT NULL,
    object_type character varying(20) NOT NULL,
    blacklist_author bigint,
    reason text,
    CONSTRAINT blacklisted_object_type_check CHECK (((object_type)::text = ANY (ARRAY[('user_id'::character varying)::text, ('guild_id'::character varying)::text])))
);


ALTER TABLE public.blacklisted OWNER TO postgres;

--
-- Name: blacklisted_deathinstance; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.blacklisted_deathinstance (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL
);


ALTER TABLE public.blacklisted_deathinstance OWNER TO postgres;

--
-- Name: blacklisted_users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.blacklisted_users (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL
);


ALTER TABLE public.blacklisted_users OWNER TO postgres;

--
-- Name: blunt; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.blunt (
    guild_id bigint NOT NULL,
    user_id bigint,
    puffs integer DEFAULT 0,
    total_puffs integer DEFAULT 0
);


ALTER TABLE public.blunt OWNER TO postgres;

--
-- Name: blunt_hits; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.blunt_hits (
    user_id bigint,
    taps integer DEFAULT 0,
    sparked boolean DEFAULT false,
    last_sparked timestamp without time zone
);


ALTER TABLE public.blunt_hits OWNER TO postgres;

--
-- Name: blunt_state; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.blunt_state (
    guild_id bigint NOT NULL,
    state boolean DEFAULT false
);


ALTER TABLE public.blunt_state OWNER TO postgres;

--
-- Name: boost_channels; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.boost_channels (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    message text NOT NULL
);


ALTER TABLE public.boost_channels OWNER TO postgres;

--
-- Name: boosters; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.boosters (
    user_id bigint NOT NULL,
    ts timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.boosters OWNER TO postgres;

--
-- Name: boosters_lost; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.boosters_lost (
    user_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    ts timestamp without time zone NOT NULL
);


ALTER TABLE public.boosters_lost OWNER TO postgres;

--
-- Name: br; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.br (
    guild_id bigint,
    user_id bigint,
    role_id bigint,
    status boolean DEFAULT false
);


ALTER TABLE public.br OWNER TO postgres;

--
-- Name: br_base; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.br_base (
    guild_id bigint NOT NULL,
    role_id bigint NOT NULL
);


ALTER TABLE public.br_base OWNER TO postgres;

--
-- Name: br_status; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.br_status (
    guild_id bigint,
    status boolean DEFAULT false
);


ALTER TABLE public.br_status OWNER TO postgres;

--
-- Name: button_roles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.button_roles (
    guild_id bigint NOT NULL,
    message_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    role_id bigint NOT NULL,
    emoji text,
    label text,
    style text,
    index integer NOT NULL
);


ALTER TABLE public.button_roles OWNER TO postgres;

--
-- Name: captcha_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.captcha_logs (
    user_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    result text NOT NULL,
    captcha_code text NOT NULL
);


ALTER TABLE public.captcha_logs OWNER TO postgres;

--
-- Name: captcha_settings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.captcha_settings (
    guild_id integer NOT NULL,
    role_id integer
);


ALTER TABLE public.captcha_settings OWNER TO postgres;

--
-- Name: captcha_verification; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.captcha_verification (
    guild_id bigint NOT NULL,
    verification_channel bigint,
    logs_channel bigint,
    verification_role bigint,
    user_id bigint,
    username text NOT NULL,
    verified boolean DEFAULT false
);


ALTER TABLE public.captcha_verification OWNER TO postgres;

--
-- Name: captcha_verified; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.captcha_verified (
    guild_id bigint NOT NULL,
    verification_channel bigint,
    logs_channel bigint,
    verification_role bigint,
    username text,
    user_id bigint,
    verified boolean DEFAULT false
);


ALTER TABLE public.captcha_verified OWNER TO postgres;

--
-- Name: card_messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.card_messages (
    user_id bigint NOT NULL,
    message_count integer DEFAULT 0,
    global_rank integer DEFAULT 1,
    guild_id bigint
);


ALTER TABLE public.card_messages OWNER TO postgres;

--
-- Name: cards_messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cards_messages (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    message_count integer DEFAULT 0,
    global_rank integer DEFAULT 1
);


ALTER TABLE public.cards_messages OWNER TO postgres;

--
-- Name: channelban; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.channelban (
    guild_id bigint NOT NULL,
    role_id bigint
);


ALTER TABLE public.channelban OWNER TO postgres;

--
-- Name: chatfilter; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.chatfilter (
    word text NOT NULL,
    guild bigint NOT NULL
);


ALTER TABLE public.chatfilter OWNER TO postgres;

--
-- Name: cmderror; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cmderror (
    code text NOT NULL,
    description text NOT NULL
);


ALTER TABLE public.cmderror OWNER TO postgres;

--
-- Name: command_restriction; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.command_restriction (
    guild_id bigint NOT NULL,
    command_name character varying(255) NOT NULL,
    role_id bigint NOT NULL
);


ALTER TABLE public.command_restriction OWNER TO postgres;

--
-- Name: command_usage; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.command_usage (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    command_name text NOT NULL,
    command_type text NOT NULL,
    uses integer DEFAULT 0
);


ALTER TABLE public.command_usage OWNER TO postgres;

--
-- Name: companies; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.companies (
    user_id bigint NOT NULL,
    company_name text NOT NULL,
    balance bigint DEFAULT 0,
    invested boolean DEFAULT false,
    message_count integer DEFAULT 0,
    storage_capacity bigint DEFAULT 1000000,
    upgrade_level integer DEFAULT 0,
    current_storage bigint DEFAULT 0,
    earnings_rate integer DEFAULT 0,
    activity_level character varying(10) DEFAULT 'low'::character varying,
    invested_amount bigint DEFAULT 0,
    investment_storage bigint DEFAULT 0,
    investment_rate bigint DEFAULT 0,
    investment_capacity bigint DEFAULT 1000000
);


ALTER TABLE public.companies OWNER TO postgres;

--
-- Name: confess; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.confess (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    confession integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.confess OWNER TO postgres;

--
-- Name: confess_members; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.confess_members (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    confession integer NOT NULL
);


ALTER TABLE public.confess_members OWNER TO postgres;

--
-- Name: confess_mute; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.confess_mute (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL
);


ALTER TABLE public.confess_mute OWNER TO postgres;

--
-- Name: confession_channels; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.confession_channels (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL
);


ALTER TABLE public.confession_channels OWNER TO postgres;

--
-- Name: context; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.context (
    guild_id bigint NOT NULL,
    success_color character varying(50),
    success_emoji character varying(50),
    fail_color character varying(50),
    fail_emoji character varying(50),
    warning_color character varying(50),
    warning_emoji character varying(50)
);


ALTER TABLE public.context OWNER TO postgres;

--
-- Name: counter_channels; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.counter_channels (
    channel_id bigint NOT NULL,
    current_count integer NOT NULL
);


ALTER TABLE public.counter_channels OWNER TO postgres;

--
-- Name: diary; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.diary (
    user_id bigint NOT NULL,
    date text NOT NULL,
    title text NOT NULL,
    text text NOT NULL
);


ALTER TABLE public.diary OWNER TO postgres;

--
-- Name: disabled_commands; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.disabled_commands (
    guild_id bigint,
    status boolean,
    whitelist bigint[],
    command text,
    channels text DEFAULT ''::text NOT NULL
);


ALTER TABLE public.disabled_commands OWNER TO postgres;

--
-- Name: disabled_modules; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.disabled_modules (
    guild_id bigint,
    module text
);


ALTER TABLE public.disabled_modules OWNER TO postgres;

--
-- Name: donators; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.donators (
    user_id bigint NOT NULL,
    ts timestamp without time zone NOT NULL
);


ALTER TABLE public.donators OWNER TO postgres;

--
-- Name: earnings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.earnings (
    user_id bigint NOT NULL,
    h0 numeric(15,2) DEFAULT 0,
    h1 numeric(50,2) DEFAULT 0,
    h2 numeric(50,2) DEFAULT 0,
    h3 numeric(50,2) DEFAULT 0,
    h4 numeric(50,2) DEFAULT 0,
    h5 numeric(50,2) DEFAULT 0,
    h6 numeric(50,2) DEFAULT 0,
    h7 numeric(50,2) DEFAULT 0,
    h8 numeric(50,2) DEFAULT 0,
    h9 numeric(50,2) DEFAULT 0,
    h10 numeric(50,2) DEFAULT 0,
    h11 numeric(50,2) DEFAULT 0,
    h12 numeric(50,2) DEFAULT 0,
    h13 numeric(50,2) DEFAULT 0,
    h14 numeric(50,2) DEFAULT 0,
    h15 numeric(50,2) DEFAULT 0,
    h16 numeric(50,2) DEFAULT 0,
    h17 numeric(50,2) DEFAULT 0,
    h18 numeric(50,2) DEFAULT 0,
    h19 numeric(50,2) DEFAULT 0,
    h20 numeric(50,2) DEFAULT 0,
    h21 numeric(50,2) DEFAULT 0,
    h22 numeric(50,2) DEFAULT 0,
    h23 numeric(50,2) DEFAULT 0,
    h24 numeric(50,2) DEFAULT 0,
    h25 numeric(50,2) DEFAULT 0
);


ALTER TABLE public.earnings OWNER TO postgres;

--
-- Name: economy; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.economy (
    user_id bigint NOT NULL,
    balance numeric(50,2) DEFAULT 0,
    earnings numeric(50,2) DEFAULT 0,
    wins integer DEFAULT 0,
    total numeric(50,2) DEFAULT 0,
    bank numeric(50,2) DEFAULT 0,
    CONSTRAINT economy_balance_check CHECK ((balance >= (0)::numeric)),
    CONSTRAINT economy_bank_check CHECK ((bank >= (0)::numeric)),
    CONSTRAINT economy_total_check CHECK ((total >= (0)::numeric)),
    CONSTRAINT economy_wins_check CHECK ((wins >= 0))
);


ALTER TABLE public.economy OWNER TO postgres;

--
-- Name: ended_giveaways; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ended_giveaways (
    guild_id bigint NOT NULL,
    message_id bigint NOT NULL,
    channel_id bigint,
    prize text,
    winner_count integer,
    creator_id bigint,
    ended_at timestamp without time zone
);


ALTER TABLE public.ended_giveaways OWNER TO postgres;

--
-- Name: fakeperms; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.fakeperms (
    guild_id bigint NOT NULL,
    role_id bigint NOT NULL,
    perms text
);


ALTER TABLE public.fakeperms OWNER TO postgres;

--
-- Name: filter; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.filter (
    guild_id bigint NOT NULL,
    keyword character varying(32) NOT NULL
);


ALTER TABLE public.filter OWNER TO postgres;

--
-- Name: filter_event; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.filter_event (
    guild_id bigint NOT NULL,
    event character varying(32) NOT NULL,
    is_enabled boolean DEFAULT true,
    threshold smallint DEFAULT 2
);


ALTER TABLE public.filter_event OWNER TO postgres;

--
-- Name: filter_setup; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.filter_setup (
    guild_id bigint NOT NULL,
    punishment text
);


ALTER TABLE public.filter_setup OWNER TO postgres;

--
-- Name: filter_snipe; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.filter_snipe (
    guild_id bigint NOT NULL,
    invites boolean DEFAULT false,
    links boolean DEFAULT false,
    images boolean DEFAULT false,
    words boolean DEFAULT false
);


ALTER TABLE public.filter_snipe OWNER TO postgres;

--
-- Name: filter_whitelist; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.filter_whitelist (
    guild_id bigint,
    events text,
    user_id bigint
);


ALTER TABLE public.filter_whitelist OWNER TO postgres;

--
-- Name: forcenick; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.forcenick (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    nick text NOT NULL
);


ALTER TABLE public.forcenick OWNER TO postgres;

--
-- Name: forcenickname; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.forcenickname (
    guild_id bigint,
    user_id bigint,
    nickname text
);


ALTER TABLE public.forcenickname OWNER TO postgres;

--
-- Name: freaky; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.freaky (
    user_id bigint NOT NULL,
    target_id bigint NOT NULL,
    times_fucked integer DEFAULT 1
);


ALTER TABLE public.freaky OWNER TO postgres;

--
-- Name: gang_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.gang_logs (
    id integer NOT NULL,
    log_channel_id bigint NOT NULL
);


ALTER TABLE public.gang_logs OWNER TO postgres;

--
-- Name: gang_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.gang_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.gang_logs_id_seq OWNER TO postgres;

--
-- Name: gang_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.gang_logs_id_seq OWNED BY public.gang_logs.id;


--
-- Name: gang_members; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.gang_members (
    user_id bigint NOT NULL,
    gang_name text NOT NULL,
    role text NOT NULL,
    toggle text DEFAULT 'off'::text
);


ALTER TABLE public.gang_members OWNER TO postgres;

--
-- Name: gangs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.gangs (
    gang_name text NOT NULL,
    owner_id bigint NOT NULL,
    created_at text NOT NULL,
    banner_url text
);


ALTER TABLE public.gangs OWNER TO postgres;

--
-- Name: giveaway_blacklist; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.giveaway_blacklist (
    guild_id bigint NOT NULL,
    role_id bigint NOT NULL
);


ALTER TABLE public.giveaway_blacklist OWNER TO postgres;

--
-- Name: giveaway_config; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.giveaway_config (
    guild_id bigint NOT NULL,
    dm_creator boolean DEFAULT false,
    dm_winners boolean DEFAULT false
);


ALTER TABLE public.giveaway_config OWNER TO postgres;

--
-- Name: giveaway_entries; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.giveaway_entries (
    guild_id bigint NOT NULL,
    message_id bigint NOT NULL,
    user_id bigint NOT NULL,
    entry_count integer DEFAULT 1
);


ALTER TABLE public.giveaway_entries OWNER TO postgres;

--
-- Name: giveaway_settings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.giveaway_settings (
    guild_id bigint NOT NULL,
    role_id bigint NOT NULL,
    entries integer DEFAULT 0
);


ALTER TABLE public.giveaway_settings OWNER TO postgres;

--
-- Name: giveaway_templates; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.giveaway_templates (
    guild_id bigint NOT NULL,
    code character varying(255)
);


ALTER TABLE public.giveaway_templates OWNER TO postgres;

--
-- Name: globalbans; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.globalbans (
    user_id bigint NOT NULL,
    reason text
);


ALTER TABLE public.globalbans OWNER TO postgres;

--
-- Name: goodbye_channels; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.goodbye_channels (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    message text NOT NULL
);


ALTER TABLE public.goodbye_channels OWNER TO postgres;

--
-- Name: graph_color; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.graph_color (
    user_id bigint NOT NULL,
    color character varying(50)
);


ALTER TABLE public.graph_color OWNER TO postgres;

--
-- Name: guild_invites; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.guild_invites (
    guild_id bigint NOT NULL,
    invite text NOT NULL
);


ALTER TABLE public.guild_invites OWNER TO postgres;

--
-- Name: guild_notifications; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.guild_notifications (
    guild_id bigint NOT NULL,
    notified_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.guild_notifications OWNER TO postgres;

--
-- Name: guild_settings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.guild_settings (
    guild_id bigint NOT NULL,
    report_channel_id bigint
);


ALTER TABLE public.guild_settings OWNER TO postgres;

--
-- Name: guilds; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.guilds (
    guild_id bigint NOT NULL,
    autoboard_channel bigint,
    level_up_message text,
    text_xp_rate double precision DEFAULT 1.0,
    voice_xp_rate double precision DEFAULT 1.0
);


ALTER TABLE public.guilds OWNER TO postgres;

--
-- Name: guilds_stats; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.guilds_stats (
    guild_id bigint NOT NULL,
    joins integer DEFAULT 0,
    leaves integer DEFAULT 0
);


ALTER TABLE public.guilds_stats OWNER TO postgres;

--
-- Name: gw; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.gw (
    guild_id bigint NOT NULL,
    channel_id bigint,
    message_id bigint NOT NULL,
    ex timestamp without time zone,
    creator bigint,
    winner_count integer DEFAULT 1,
    prize text
);


ALTER TABLE public.gw OWNER TO postgres;

--
-- Name: hardban; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.hardban (
    guild_id bigint,
    user_id bigint
);


ALTER TABLE public.hardban OWNER TO postgres;

--
-- Name: highlight; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.highlight (
    user_id bigint NOT NULL,
    word text NOT NULL,
    strict boolean DEFAULT false
);


ALTER TABLE public.highlight OWNER TO postgres;

--
-- Name: hunted_animals; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.hunted_animals (
    user_id bigint NOT NULL,
    animal_name text NOT NULL,
    count integer DEFAULT 0
);


ALTER TABLE public.hunted_animals OWNER TO postgres;

--
-- Name: hunters; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.hunters (
    user_id bigint NOT NULL
);


ALTER TABLE public.hunters OWNER TO postgres;

--
-- Name: imageonly; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.imageonly (
    channel_id bigint NOT NULL
);


ALTER TABLE public.imageonly OWNER TO postgres;

--
-- Name: instagram; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.instagram (
    channel_id bigint,
    guild_id bigint,
    username text,
    sent text
);


ALTER TABLE public.instagram OWNER TO postgres;

--
-- Name: instance_whitelist; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.instance_whitelist (
    user_id bigint NOT NULL,
    expiration timestamp with time zone
);


ALTER TABLE public.instance_whitelist OWNER TO postgres;

--
-- Name: instances; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.instances (
    token text NOT NULL,
    user_id bigint NOT NULL,
    bot_id bigint NOT NULL,
    guild_id bigint,
    status_text text,
    status_type integer
);


ALTER TABLE public.instances OWNER TO postgres;

--
-- Name: interactions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.interactions (
    user1_id bigint NOT NULL,
    user2_id bigint NOT NULL,
    interaction character varying(255) NOT NULL,
    count integer DEFAULT 1 NOT NULL
);


ALTER TABLE public.interactions OWNER TO postgres;

--
-- Name: inventory; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.inventory (
    user_id bigint,
    item character varying(255),
    amount integer
);


ALTER TABLE public.inventory OWNER TO postgres;

--
-- Name: invoke; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.invoke (
    guild_id bigint NOT NULL,
    cmd text NOT NULL,
    message text NOT NULL
);


ALTER TABLE public.invoke OWNER TO postgres;

--
-- Name: jail_config; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.jail_config (
    guild_id bigint NOT NULL,
    role_id bigint,
    channel_id bigint
);


ALTER TABLE public.jail_config OWNER TO postgres;

--
-- Name: jailed; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.jailed (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    roles text NOT NULL
);


ALTER TABLE public.jailed OWNER TO postgres;

--
-- Name: join_dm_settings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.join_dm_settings (
    guild_id bigint NOT NULL,
    message text,
    enabled boolean DEFAULT true
);


ALTER TABLE public.join_dm_settings OWNER TO postgres;

--
-- Name: labs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.labs (
    user_id bigint NOT NULL,
    level integer DEFAULT 1,
    ampoules integer DEFAULT 1,
    earnings bigint DEFAULT 0,
    storage bigint DEFAULT 164571
);


ALTER TABLE public.labs OWNER TO postgres;

--
-- Name: lastfm; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.lastfm (
    user_id bigint NOT NULL,
    username text NOT NULL
);


ALTER TABLE public.lastfm OWNER TO postgres;

--
-- Name: lastfm_commands; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.lastfm_commands (
    user_id bigint NOT NULL,
    command text NOT NULL
);


ALTER TABLE public.lastfm_commands OWNER TO postgres;

--
-- Name: lastfm_crowns; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.lastfm_crowns (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    username text,
    artist text NOT NULL,
    plays bigint,
    album text
);


ALTER TABLE public.lastfm_crowns OWNER TO postgres;

--
-- Name: lastfm_embeds; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.lastfm_embeds (
    user_id bigint NOT NULL,
    embed_code text NOT NULL
);


ALTER TABLE public.lastfm_embeds OWNER TO postgres;

--
-- Name: lastfm_likes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.lastfm_likes (
    user_id bigint,
    track text,
    artist text
);


ALTER TABLE public.lastfm_likes OWNER TO postgres;

--
-- Name: leave; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.leave (
    guild_id bigint,
    channel_id bigint,
    message text
);


ALTER TABLE public.leave OWNER TO postgres;

--
-- Name: lf_reactions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.lf_reactions (
    user_id bigint NOT NULL,
    up text,
    down text
);


ALTER TABLE public.lf_reactions OWNER TO postgres;

--
-- Name: lock_role; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.lock_role (
    guild_id bigint NOT NULL,
    role_id bigint
);


ALTER TABLE public.lock_role OWNER TO postgres;

--
-- Name: logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.logs (
    id integer NOT NULL,
    guild_id bigint NOT NULL,
    moderator_id bigint,
    user_id bigint,
    event_type text NOT NULL,
    description text,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.logs OWNER TO postgres;

--
-- Name: logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.logs_id_seq OWNER TO postgres;

--
-- Name: logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.logs_id_seq OWNED BY public.logs.id;


--
-- Name: lottery; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.lottery (
    id integer NOT NULL,
    jackpot bigint DEFAULT 1000
);


ALTER TABLE public.lottery OWNER TO postgres;

--
-- Name: lottery_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.lottery_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.lottery_id_seq OWNER TO postgres;

--
-- Name: lottery_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.lottery_id_seq OWNED BY public.lottery.id;


--
-- Name: marriages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.marriages (
    user1_id bigint,
    user2_id bigint
);


ALTER TABLE public.marriages OWNER TO postgres;

--
-- Name: mentions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.mentions (
    id integer NOT NULL,
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    author_id bigint NOT NULL,
    message_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    mention_type text NOT NULL,
    "timestamp" bigint NOT NULL,
    attachments text,
    mentioned_user_id bigint
);


ALTER TABLE public.mentions OWNER TO postgres;

--
-- Name: mentions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.mentions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.mentions_id_seq OWNER TO postgres;

--
-- Name: mentions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.mentions_id_seq OWNED BY public.mentions.id;


--
-- Name: message_activity; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.message_activity (
    user_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    message_count bigint DEFAULT 0 NOT NULL
);


ALTER TABLE public.message_activity OWNER TO postgres;

--
-- Name: message_count; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.message_count (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    count integer DEFAULT 0
);


ALTER TABLE public.message_count OWNER TO postgres;

--
-- Name: mod_mail; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.mod_mail (
    guild_id integer NOT NULL,
    mod_channel_id integer NOT NULL
);


ALTER TABLE public.mod_mail OWNER TO postgres;

--
-- Name: moderation_channel; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.moderation_channel (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    category_id bigint
);


ALTER TABLE public.moderation_channel OWNER TO postgres;

--
-- Name: moderation_events; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.moderation_events (
    id integer NOT NULL,
    guild_id bigint NOT NULL,
    event_name text NOT NULL,
    target_id bigint,
    action_taken text,
    reason text,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.moderation_events OWNER TO postgres;

--
-- Name: moderation_events_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.moderation_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.moderation_events_id_seq OWNER TO postgres;

--
-- Name: moderation_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.moderation_events_id_seq OWNED BY public.moderation_events.id;


--
-- Name: moderation_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.moderation_logs (
    id bigint NOT NULL,
    guild_id bigint NOT NULL,
    user_id bigint,
    action_type character varying(255) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.moderation_logs OWNER TO postgres;

--
-- Name: moderation_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.moderation_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.moderation_logs_id_seq OWNER TO postgres;

--
-- Name: moderation_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.moderation_logs_id_seq OWNED BY public.moderation_logs.id;


--
-- Name: moderation_statistics; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.moderation_statistics (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    data jsonb
);


ALTER TABLE public.moderation_statistics OWNER TO postgres;

--
-- Name: modlog_queue; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.modlog_queue (
    id integer NOT NULL,
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    embed_data jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.modlog_queue OWNER TO postgres;

--
-- Name: modlog_queue_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.modlog_queue_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.modlog_queue_id_seq OWNER TO postgres;

--
-- Name: modlog_queue_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.modlog_queue_id_seq OWNED BY public.modlog_queue.id;


--
-- Name: names; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.names (
    user_id bigint NOT NULL,
    type character varying(50),
    username character varying(255) NOT NULL,
    ts timestamp without time zone NOT NULL
);


ALTER TABLE public.names OWNER TO postgres;

--
-- Name: niggertalk; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.niggertalk (
    webhook text NOT NULL,
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    user_id bigint NOT NULL
);


ALTER TABLE public.niggertalk OWNER TO postgres;

--
-- Name: notifications; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.notifications (
    guild_id bigint NOT NULL,
    channels jsonb,
    role_id bigint,
    message text,
    command boolean DEFAULT false
);


ALTER TABLE public.notifications OWNER TO postgres;

--
-- Name: nsfw_stats; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.nsfw_stats (
    user_id integer NOT NULL,
    target_id integer NOT NULL,
    times_fucked integer
);


ALTER TABLE public.nsfw_stats OWNER TO postgres;

--
-- Name: nword; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.nword (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    count integer DEFAULT 1
);


ALTER TABLE public.nword OWNER TO postgres;

--
-- Name: offensive; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.offensive (
    user_id bigint NOT NULL,
    count bigint DEFAULT 0,
    hard_r_count integer DEFAULT 0,
    general_count integer DEFAULT 0
);


ALTER TABLE public.offensive OWNER TO postgres;

--
-- Name: offensive_words; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.offensive_words (
    user_id bigint NOT NULL,
    count bigint DEFAULT 0
);


ALTER TABLE public.offensive_words OWNER TO postgres;

--
-- Name: opened_ticket_topics; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opened_ticket_topics (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    topic_name text
);


ALTER TABLE public.opened_ticket_topics OWNER TO postgres;

--
-- Name: opened_tickets; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opened_tickets (
    guild_id bigint,
    channel_id bigint NOT NULL,
    user_id bigint
);


ALTER TABLE public.opened_tickets OWNER TO postgres;

--
-- Name: paginator; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.paginator (
    guild_id bigint NOT NULL,
    name text NOT NULL,
    embeds jsonb NOT NULL
);


ALTER TABLE public.paginator OWNER TO postgres;

--
-- Name: pfps; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.pfps (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL
);


ALTER TABLE public.pfps OWNER TO postgres;

--
-- Name: pingonjoin; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.pingonjoin (
    guild_id bigint,
    channel_id bigint,
    threshold integer,
    message text
);


ALTER TABLE public.pingonjoin OWNER TO postgres;

--
-- Name: poj_channels; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.poj_channels (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL
);


ALTER TABLE public.poj_channels OWNER TO postgres;

--
-- Name: prefixes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.prefixes (
    guild_id bigint NOT NULL,
    prefix text
);


ALTER TABLE public.prefixes OWNER TO postgres;

--
-- Name: premium_users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.premium_users (
    user_id bigint NOT NULL,
    ts timestamp without time zone
);


ALTER TABLE public.premium_users OWNER TO postgres;

--
-- Name: premiumrole; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.premiumrole (
    guild_id bigint NOT NULL,
    role_id bigint
);


ALTER TABLE public.premiumrole OWNER TO postgres;

--
-- Name: protected; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.protected (
    guild_id bigint NOT NULL,
    user_ids bigint[] NOT NULL
);


ALTER TABLE public.protected OWNER TO postgres;

--
-- Name: protected_roles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.protected_roles (
    guild_id bigint NOT NULL,
    role_id bigint NOT NULL
);


ALTER TABLE public.protected_roles OWNER TO postgres;

--
-- Name: reaction_triggers; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.reaction_triggers (
    guild_id bigint NOT NULL,
    trigger text NOT NULL,
    reaction text NOT NULL,
    strict boolean DEFAULT false
);


ALTER TABLE public.reaction_triggers OWNER TO postgres;

--
-- Name: reactionrole; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.reactionrole (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    message_id bigint NOT NULL,
    emoji text NOT NULL,
    role_id bigint NOT NULL,
    message_url text NOT NULL
);


ALTER TABLE public.reactionrole OWNER TO postgres;

--
-- Name: reminders; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.reminders (
    user_id bigint NOT NULL,
    guild_id bigint,
    channel_id bigint,
    reminder text,
    "time" timestamp without time zone
);


ALTER TABLE public.reminders OWNER TO postgres;

--
-- Name: report_channel; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.report_channel (
    guild_id bigint NOT NULL,
    channel_id bigint
);


ALTER TABLE public.report_channel OWNER TO postgres;

--
-- Name: report_whitelist; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.report_whitelist (
    user_id bigint NOT NULL
);


ALTER TABLE public.report_whitelist OWNER TO postgres;

--
-- Name: reskin; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.reskin (
    user_id bigint NOT NULL,
    username text,
    avatar_url text
);


ALTER TABLE public.reskin OWNER TO postgres;

--
-- Name: reskin_config; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.reskin_config (
    guild_id bigint NOT NULL,
    reskin jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE public.reskin_config OWNER TO postgres;

--
-- Name: revive; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.revive (
    guild_id bigint NOT NULL,
    channel_id bigint,
    message text,
    is_embed boolean DEFAULT false,
    enabled boolean DEFAULT false
);


ALTER TABLE public.revive OWNER TO postgres;

--
-- Name: rolelock; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.rolelock (
    id integer NOT NULL,
    guild_id bigint NOT NULL,
    locker_role bigint NOT NULL,
    locked_role bigint NOT NULL,
    authorized_user_ids bigint[]
);


ALTER TABLE public.rolelock OWNER TO postgres;

--
-- Name: rolelock_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.rolelock_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.rolelock_id_seq OWNER TO postgres;

--
-- Name: rolelock_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.rolelock_id_seq OWNED BY public.rolelock.id;


--
-- Name: screentime; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.screentime (
    user_id bigint NOT NULL,
    online bigint DEFAULT 1,
    offline bigint DEFAULT 1,
    idle bigint DEFAULT 1,
    dnd bigint DEFAULT 1
);


ALTER TABLE public.screentime OWNER TO postgres;

--
-- Name: self_prefixes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.self_prefixes (
    guild_id bigint NOT NULL,
    prefix text
);


ALTER TABLE public.self_prefixes OWNER TO postgres;

--
-- Name: selfprefix; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.selfprefix (
    user_id bigint NOT NULL,
    prefix text
);


ALTER TABLE public.selfprefix OWNER TO postgres;

--
-- Name: server_activity; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.server_activity (
    user_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    message_count bigint DEFAULT 0 NOT NULL
);


ALTER TABLE public.server_activity OWNER TO postgres;

--
-- Name: server_settings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.server_settings (
    guild_id bigint NOT NULL,
    private_server_enabled boolean DEFAULT false,
    antiraid_enabled boolean DEFAULT false,
    minimum_account_age integer DEFAULT 7,
    lockdown boolean DEFAULT false,
    default_pfp_check boolean DEFAULT false,
    log_channel_id bigint,
    raid_punishment text DEFAULT 'ban'::text
);


ALTER TABLE public.server_settings OWNER TO postgres;

--
-- Name: snapchat; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.snapchat (
    guild_id bigint,
    channel_id bigint,
    username text,
    stories bigint,
    highlights bigint
);


ALTER TABLE public.snapchat OWNER TO postgres;

--
-- Name: sp2; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sp2 (
    user_id bigint NOT NULL,
    prefix text NOT NULL
);


ALTER TABLE public.sp2 OWNER TO postgres;

--
-- Name: starboard; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.starboard (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    emoji character varying(50) NOT NULL,
    threshold integer NOT NULL
);


ALTER TABLE public.starboard OWNER TO postgres;

--
-- Name: starboard_entries; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.starboard_entries (
    guild_id bigint NOT NULL,
    starboard_message_id bigint NOT NULL,
    channel_id bigint,
    message_id bigint,
    emoji character varying(50)
);


ALTER TABLE public.starboard_entries OWNER TO postgres;

--
-- Name: starboard_ignored; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.starboard_ignored (
    id integer NOT NULL,
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL
);


ALTER TABLE public.starboard_ignored OWNER TO postgres;

--
-- Name: starboard_ignored_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.starboard_ignored_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.starboard_ignored_id_seq OWNER TO postgres;

--
-- Name: starboard_ignored_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.starboard_ignored_id_seq OWNED BY public.starboard_ignored.id;


--
-- Name: steal_disabled; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.steal_disabled (
    guild_id bigint NOT NULL
);


ALTER TABLE public.steal_disabled OWNER TO postgres;

--
-- Name: sticky_messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sticky_messages (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    message text NOT NULL
);


ALTER TABLE public.sticky_messages OWNER TO postgres;

--
-- Name: suggestions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.suggestions (
    message_id bigint NOT NULL,
    upvotes integer NOT NULL,
    downvotes integer NOT NULL
);


ALTER TABLE public.suggestions OWNER TO postgres;

--
-- Name: supergamble_data; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.supergamble_data (
    user_id bigint NOT NULL,
    last_reset integer NOT NULL,
    wins integer DEFAULT 0 NOT NULL,
    guaranteed integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.supergamble_data OWNER TO postgres;

--
-- Name: system_messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.system_messages (
    guild_id bigint NOT NULL
);


ALTER TABLE public.system_messages OWNER TO postgres;

--
-- Name: terms_agreement; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.terms_agreement (
    user_id bigint NOT NULL,
    state boolean DEFAULT false
);


ALTER TABLE public.terms_agreement OWNER TO postgres;

--
-- Name: text_level_settings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.text_level_settings (
    guild_id bigint NOT NULL,
    award_message text,
    roles text
);


ALTER TABLE public.text_level_settings OWNER TO postgres;

--
-- Name: text_levels; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.text_levels (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    xp integer DEFAULT 0,
    msgs integer DEFAULT 0
);


ALTER TABLE public.text_levels OWNER TO postgres;

--
-- Name: ticket_topic_categories; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ticket_topic_categories (
    guild_id bigint NOT NULL,
    topic_name text NOT NULL,
    category_id bigint
);


ALTER TABLE public.ticket_topic_categories OWNER TO postgres;

--
-- Name: ticket_topic_roles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ticket_topic_roles (
    guild_id bigint NOT NULL,
    topic_name text NOT NULL,
    role_id bigint NOT NULL
);


ALTER TABLE public.ticket_topic_roles OWNER TO postgres;

--
-- Name: ticket_topics; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ticket_topics (
    guild_id bigint NOT NULL,
    name character varying(100) NOT NULL,
    description text
);


ALTER TABLE public.ticket_topics OWNER TO postgres;

--
-- Name: tickets; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tickets (
    guild_id bigint NOT NULL,
    category_id bigint,
    support_id bigint,
    open_embed text,
    open_emoji character varying(10),
    delete_emoji character varying(10),
    message_id bigint,
    channel_id bigint
);


ALTER TABLE public.tickets OWNER TO postgres;

--
-- Name: timezone; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.timezone (
    user_id bigint NOT NULL,
    tz text
);


ALTER TABLE public.timezone OWNER TO postgres;

--
-- Name: traceback; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.traceback (
    command character varying(100),
    error_code character varying(100) NOT NULL,
    error_message text NOT NULL,
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    user_id bigint NOT NULL,
    content text NOT NULL
);


ALTER TABLE public.traceback OWNER TO postgres;

--
-- Name: tracking_channels; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tracking_channels (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL
);


ALTER TABLE public.tracking_channels OWNER TO postgres;

--
-- Name: used_items; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.used_items (
    user_id bigint,
    item character varying(255),
    ts timestamp without time zone,
    expiration timestamp without time zone
);


ALTER TABLE public.used_items OWNER TO postgres;

--
-- Name: user_fish; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_fish (
    user_id bigint NOT NULL,
    fish_caught text DEFAULT ''::text
);


ALTER TABLE public.user_fish OWNER TO postgres;

--
-- Name: user_levels; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_levels (
    user_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    level integer DEFAULT 1,
    xp integer DEFAULT 0
);


ALTER TABLE public.user_levels OWNER TO postgres;

--
-- Name: usercard_messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.usercard_messages (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    message_count integer DEFAULT 0,
    global_rank integer DEFAULT 1
);


ALTER TABLE public.usercard_messages OWNER TO postgres;

--
-- Name: username_changes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.username_changes (
    user_id bigint NOT NULL,
    username text NOT NULL,
    change_time timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.username_changes OWNER TO postgres;

--
-- Name: uwulock; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.uwulock (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    webhook character varying(255),
    webhook_url text DEFAULT ''::text NOT NULL
);


ALTER TABLE public.uwulock OWNER TO postgres;

--
-- Name: vanity; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.vanity (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    message text
);


ALTER TABLE public.vanity OWNER TO postgres;

--
-- Name: vanity_roles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.vanity_roles (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL
);


ALTER TABLE public.vanity_roles OWNER TO postgres;

--
-- Name: vanity_status; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.vanity_status (
    guild_id bigint NOT NULL,
    role_id bigint,
    channel_id bigint,
    message text
);


ALTER TABLE public.vanity_status OWNER TO postgres;

--
-- Name: vape; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.vape (
    guild_id bigint NOT NULL,
    holder bigint,
    guild_hits integer DEFAULT 0
);


ALTER TABLE public.vape OWNER TO postgres;

--
-- Name: vape_flavors; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.vape_flavors (
    user_id bigint NOT NULL,
    flavor text
);


ALTER TABLE public.vape_flavors OWNER TO postgres;

--
-- Name: vcbans; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.vcbans (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL
);


ALTER TABLE public.vcbans OWNER TO postgres;

--
-- Name: verification_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.verification_logs (
    user_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    result text NOT NULL,
    captcha_code text NOT NULL
);


ALTER TABLE public.verification_logs OWNER TO postgres;

--
-- Name: verified_users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.verified_users (
    user_id integer NOT NULL
);


ALTER TABLE public.verified_users OWNER TO postgres;

--
-- Name: vm_status; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.vm_status (
    user_id bigint NOT NULL,
    status text
);


ALTER TABLE public.vm_status OWNER TO postgres;

--
-- Name: voice_activity; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.voice_activity (
    user_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    time_in_voice interval DEFAULT '00:00:00'::interval NOT NULL
);


ALTER TABLE public.voice_activity OWNER TO postgres;

--
-- Name: voice_levels; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.voice_levels (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    xp integer DEFAULT 0,
    time_spent integer DEFAULT 0
);


ALTER TABLE public.voice_levels OWNER TO postgres;

--
-- Name: voicemaster; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.voicemaster (
    category_id bigint,
    voicechannel_id bigint,
    channel_id bigint,
    message_id bigint,
    guild_id bigint,
    category bigint
);


ALTER TABLE public.voicemaster OWNER TO postgres;

--
-- Name: voicemaster_data; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.voicemaster_data (
    channel_id bigint,
    guild_id bigint,
    owner_id bigint
);


ALTER TABLE public.voicemaster_data OWNER TO postgres;

--
-- Name: voicetime_overall; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.voicetime_overall (
    user_id bigint NOT NULL,
    vc1 numeric DEFAULT 0.0,
    vc2 numeric DEFAULT 0.0,
    vc3 numeric DEFAULT 0.0,
    vc4 numeric DEFAULT 0.0,
    vc5 numeric DEFAULT 0.0,
    channel_id bigint
);


ALTER TABLE public.voicetime_overall OWNER TO postgres;

--
-- Name: warning_punishments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.warning_punishments (
    guild_id bigint NOT NULL,
    threshold integer NOT NULL,
    type text,
    duration integer
);


ALTER TABLE public.warning_punishments OWNER TO postgres;

--
-- Name: warnings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.warnings (
    id text NOT NULL,
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    reason text NOT NULL,
    created_at timestamp without time zone NOT NULL,
    moderator_id bigint NOT NULL
);


ALTER TABLE public.warnings OWNER TO postgres;

--
-- Name: welcome; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.welcome (
    guild_id bigint,
    channel_id bigint,
    message text
);


ALTER TABLE public.welcome OWNER TO postgres;

--
-- Name: welcome_channels; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.welcome_channels (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    message text NOT NULL
);


ALTER TABLE public.welcome_channels OWNER TO postgres;

--
-- Name: whitelist; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.whitelist (
    user_id bigint NOT NULL
);


ALTER TABLE public.whitelist OWNER TO postgres;

--
-- Name: whitelisted; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.whitelisted (
    guild bigint,
    user_id bigint
);


ALTER TABLE public.whitelisted OWNER TO postgres;

--
-- Name: word_counts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.word_counts (
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    word text NOT NULL,
    count integer
);


ALTER TABLE public.word_counts OWNER TO postgres;

--
-- Name: main; Type: TABLE; Schema: reaction_roles; Owner: postgres
--

CREATE TABLE reaction_roles.main (
    guild_id bigint NOT NULL,
    message_id bigint NOT NULL,
    role_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    emoji text NOT NULL
);


ALTER TABLE reaction_roles.main OWNER TO postgres;

--
-- Name: roles; Type: TABLE; Schema: reaction_roles; Owner: postgres
--

CREATE TABLE reaction_roles.roles (
    guild_id bigint,
    role_id bigint
);


ALTER TABLE reaction_roles.roles OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: reaction_roles; Owner: postgres
--

CREATE TABLE reaction_roles.users (
    guild_id bigint,
    user_id bigint
);


ALTER TABLE reaction_roles.users OWNER TO postgres;

--
-- Name: fail; Type: TABLE; Schema: reskin; Owner: postgres
--

CREATE TABLE reskin.fail (
    user_id bigint NOT NULL,
    color text,
    emoji text
);


ALTER TABLE reskin.fail OWNER TO postgres;

--
-- Name: main; Type: TABLE; Schema: reskin; Owner: postgres
--

CREATE TABLE reskin.main (
    user_id bigint NOT NULL,
    username text,
    avatar text
);


ALTER TABLE reskin.main OWNER TO postgres;

--
-- Name: server; Type: TABLE; Schema: reskin; Owner: postgres
--

CREATE TABLE reskin.server (
    guild_id bigint NOT NULL,
    username character varying(255),
    avatar text,
    webhooks jsonb
);


ALTER TABLE reskin.server OWNER TO postgres;

--
-- Name: success; Type: TABLE; Schema: reskin; Owner: postgres
--

CREATE TABLE reskin.success (
    user_id bigint NOT NULL,
    color text,
    emoji text
);


ALTER TABLE reskin.success OWNER TO postgres;

--
-- Name: main; Type: TABLE; Schema: starboard; Owner: postgres
--

CREATE TABLE starboard.main (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    threshold integer DEFAULT 3 NOT NULL,
    emoji text DEFAULT '⭐'::text NOT NULL
);


ALTER TABLE starboard.main OWNER TO postgres;

--
-- Name: roles; Type: TABLE; Schema: starboard; Owner: postgres
--

CREATE TABLE starboard.roles (
    role_id bigint,
    guild_id bigint
);


ALTER TABLE starboard.roles OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: starboard; Owner: postgres
--

CREATE TABLE starboard.users (
    user_id bigint,
    guild_id bigint
);


ALTER TABLE starboard.users OWNER TO postgres;

--
-- Name: outages; Type: TABLE; Schema: status; Owner: postgres
--

CREATE TABLE status.outages (
    id text NOT NULL,
    title text NOT NULL,
    description text NOT NULL,
    status text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    affected_components text[] NOT NULL
);


ALTER TABLE status.outages OWNER TO postgres;

--
-- Name: active_streams; Type: TABLE; Schema: twitch; Owner: postgres
--

CREATE TABLE twitch.active_streams (
    stream_id text NOT NULL,
    username text NOT NULL,
    title text NOT NULL,
    game text NOT NULL,
    viewer_count integer NOT NULL,
    thumbnail_url text NOT NULL,
    started_at timestamp with time zone NOT NULL,
    is_live boolean DEFAULT true NOT NULL,
    notifications jsonb DEFAULT '[]'::jsonb NOT NULL,
    last_updated timestamp with time zone
);


ALTER TABLE twitch.active_streams OWNER TO postgres;

--
-- Name: custom_messages; Type: TABLE; Schema: twitch; Owner: postgres
--

CREATE TABLE twitch.custom_messages (
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    message text NOT NULL,
    is_embed boolean DEFAULT false NOT NULL
);


ALTER TABLE twitch.custom_messages OWNER TO postgres;

--
-- Name: subscriptions; Type: TABLE; Schema: twitch; Owner: postgres
--

CREATE TABLE twitch.subscriptions (
    username text NOT NULL,
    channel_id bigint NOT NULL
);


ALTER TABLE twitch.subscriptions OWNER TO postgres;

--
-- Name: channels; Type: TABLE; Schema: uwulock; Owner: postgres
--

CREATE TABLE uwulock.channels (
    channel_id bigint,
    guild_id bigint
);


ALTER TABLE uwulock.channels OWNER TO postgres;

--
-- Name: main; Type: TABLE; Schema: uwulock; Owner: postgres
--

CREATE TABLE uwulock.main (
    guild_id bigint,
    user_id bigint
);


ALTER TABLE uwulock.main OWNER TO postgres;

--
-- Name: roles; Type: TABLE; Schema: uwulock; Owner: postgres
--

CREATE TABLE uwulock.roles (
    role_id bigint,
    guild_id bigint
);


ALTER TABLE uwulock.roles OWNER TO postgres;

--
-- Name: channels; Type: TABLE; Schema: wordfilter; Owner: postgres
--

CREATE TABLE wordfilter.channels (
    channel_id bigint,
    guild_id bigint
);


ALTER TABLE wordfilter.channels OWNER TO postgres;

--
-- Name: roles; Type: TABLE; Schema: wordfilter; Owner: postgres
--

CREATE TABLE wordfilter.roles (
    role_id bigint,
    guild_id bigint
);


ALTER TABLE wordfilter.roles OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: wordfilter; Owner: postgres
--

CREATE TABLE wordfilter.users (
    user_id bigint,
    guild_id bigint
);


ALTER TABLE wordfilter.users OWNER TO postgres;

--
-- Name: activity_log log_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.activity_log ALTER COLUMN log_id SET DEFAULT nextval('public.activity_log_log_id_seq'::regclass);


--
-- Name: gang_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_logs ALTER COLUMN id SET DEFAULT nextval('public.gang_logs_id_seq'::regclass);


--
-- Name: logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.logs ALTER COLUMN id SET DEFAULT nextval('public.logs_id_seq'::regclass);


--
-- Name: lottery id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lottery ALTER COLUMN id SET DEFAULT nextval('public.lottery_id_seq'::regclass);


--
-- Name: mentions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mentions ALTER COLUMN id SET DEFAULT nextval('public.mentions_id_seq'::regclass);


--
-- Name: moderation_events id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.moderation_events ALTER COLUMN id SET DEFAULT nextval('public.moderation_events_id_seq'::regclass);


--
-- Name: moderation_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.moderation_logs ALTER COLUMN id SET DEFAULT nextval('public.moderation_logs_id_seq'::regclass);


--
-- Name: modlog_queue id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.modlog_queue ALTER COLUMN id SET DEFAULT nextval('public.modlog_queue_id_seq'::regclass);


--
-- Name: rolelock id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.rolelock ALTER COLUMN id SET DEFAULT nextval('public.rolelock_id_seq'::regclass);


--
-- Name: starboard_ignored id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.starboard_ignored ALTER COLUMN id SET DEFAULT nextval('public.starboard_ignored_id_seq'::regclass);


--
-- Name: spam spam_pkey; Type: CONSTRAINT; Schema: automod; Owner: postgres
--

ALTER TABLE ONLY automod.spam
    ADD CONSTRAINT spam_pkey PRIMARY KEY (guild_id);


--
-- Name: disabled disabled_pkey; Type: CONSTRAINT; Schema: commands; Owner: postgres
--

ALTER TABLE ONLY commands.disabled
    ADD CONSTRAINT disabled_pkey PRIMARY KEY (guild_id, channel_id, command);


--
-- Name: ban ban_guild_id_key; Type: CONSTRAINT; Schema: dm_messages; Owner: postgres
--

ALTER TABLE ONLY dm_messages.ban
    ADD CONSTRAINT ban_guild_id_key UNIQUE (guild_id);


--
-- Name: kick kick_guild_id_key; Type: CONSTRAINT; Schema: dm_messages; Owner: postgres
--

ALTER TABLE ONLY dm_messages.kick
    ADD CONSTRAINT kick_guild_id_key UNIQUE (guild_id);


--
-- Name: mute mute_guild_id_key; Type: CONSTRAINT; Schema: dm_messages; Owner: postgres
--

ALTER TABLE ONLY dm_messages.mute
    ADD CONSTRAINT mute_guild_id_key UNIQUE (guild_id);


--
-- Name: warn warn_guild_id_key; Type: CONSTRAINT; Schema: dm_messages; Owner: postgres
--

ALTER TABLE ONLY dm_messages.warn
    ADD CONSTRAINT warn_guild_id_key UNIQUE (guild_id);


--
-- Name: ban ban_guild_id_key; Type: CONSTRAINT; Schema: invoke; Owner: postgres
--

ALTER TABLE ONLY invoke.ban
    ADD CONSTRAINT ban_guild_id_key UNIQUE (guild_id);


--
-- Name: kick kick_guild_id_key; Type: CONSTRAINT; Schema: invoke; Owner: postgres
--

ALTER TABLE ONLY invoke.kick
    ADD CONSTRAINT kick_guild_id_key UNIQUE (guild_id);


--
-- Name: mute mute_guild_id_key; Type: CONSTRAINT; Schema: invoke; Owner: postgres
--

ALTER TABLE ONLY invoke.mute
    ADD CONSTRAINT mute_guild_id_key UNIQUE (guild_id);


--
-- Name: warn warn_guild_id_key; Type: CONSTRAINT; Schema: invoke; Owner: postgres
--

ALTER TABLE ONLY invoke.warn
    ADD CONSTRAINT warn_guild_id_key UNIQUE (guild_id);


--
-- Name: ce ce_pkey; Type: CONSTRAINT; Schema: lastfm; Owner: postgres
--

ALTER TABLE ONLY lastfm.ce
    ADD CONSTRAINT ce_pkey PRIMARY KEY (user_id);


--
-- Name: command command_pkey; Type: CONSTRAINT; Schema: lastfm; Owner: postgres
--

ALTER TABLE ONLY lastfm.command
    ADD CONSTRAINT command_pkey PRIMARY KEY (user_id);


--
-- Name: conf conf_pkey; Type: CONSTRAINT; Schema: lastfm; Owner: postgres
--

ALTER TABLE ONLY lastfm.conf
    ADD CONSTRAINT conf_pkey PRIMARY KEY (user_id);


--
-- Name: lastfm_likes lastfm_likes_pkey; Type: CONSTRAINT; Schema: lastfm; Owner: postgres
--

ALTER TABLE ONLY lastfm.lastfm_likes
    ADD CONSTRAINT lastfm_likes_pkey PRIMARY KEY (user_id, track, artist);


--
-- Name: conf unique_user_id; Type: CONSTRAINT; Schema: lastfm; Owner: postgres
--

ALTER TABLE ONLY lastfm.conf
    ADD CONSTRAINT unique_user_id UNIQUE (user_id);


--
-- Name: users unique_user_id_users; Type: CONSTRAINT; Schema: lastfm; Owner: postgres
--

ALTER TABLE ONLY lastfm.users
    ADD CONSTRAINT unique_user_id_users UNIQUE (user_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: lastfm; Owner: postgres
--

ALTER TABLE ONLY lastfm.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: albums albums_pkey; Type: CONSTRAINT; Schema: lastfm_library; Owner: postgres
--

ALTER TABLE ONLY lastfm_library.albums
    ADD CONSTRAINT albums_pkey PRIMARY KEY (user_id, artist, album);


--
-- Name: artists artists_pkey; Type: CONSTRAINT; Schema: lastfm_library; Owner: postgres
--

ALTER TABLE ONLY lastfm_library.artists
    ADD CONSTRAINT artists_pkey PRIMARY KEY (user_id, artist);


--
-- Name: tracks tracks_pkey; Type: CONSTRAINT; Schema: lastfm_library; Owner: postgres
--

ALTER TABLE ONLY lastfm_library.tracks
    ADD CONSTRAINT tracks_pkey PRIMARY KEY (user_id, artist, track);


--
-- Name: main main_guild_id_key; Type: CONSTRAINT; Schema: levels; Owner: postgres
--

ALTER TABLE ONLY levels.main
    ADD CONSTRAINT main_guild_id_key UNIQUE (guild_id);


--
-- Name: metrics metrics_user_id_key; Type: CONSTRAINT; Schema: levels; Owner: postgres
--

ALTER TABLE ONLY levels.metrics
    ADD CONSTRAINT metrics_user_id_key UNIQUE (user_id);


--
-- Name: achievements achievements_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.achievements
    ADD CONSTRAINT achievements_pkey PRIMARY KEY (user_id);


--
-- Name: activity_cache activity_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.activity_cache
    ADD CONSTRAINT activity_cache_pkey PRIMARY KEY (user_id, guild_id);


--
-- Name: activity_log activity_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.activity_log
    ADD CONSTRAINT activity_log_pkey PRIMARY KEY (log_id);


--
-- Name: admins_deathinstance admins_deathinstance_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admins_deathinstance
    ADD CONSTRAINT admins_deathinstance_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: afk afk_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.afk
    ADD CONSTRAINT afk_pkey PRIMARY KEY (user_id);


--
-- Name: ai_setup ai_setup_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ai_setup
    ADD CONSTRAINT ai_setup_pkey PRIMARY KEY (guild_id);


--
-- Name: aliases aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.aliases
    ADD CONSTRAINT aliases_pkey UNIQUE (guild_id, alias);


--
-- Name: antinuke_admin antinuke_admin_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.antinuke_admin
    ADD CONSTRAINT antinuke_admin_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: antinuke antinuke_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.antinuke
    ADD CONSTRAINT antinuke_pkey PRIMARY KEY (guild_id);


--
-- Name: antinuke_threshold antinuke_threshold_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.antinuke_threshold
    ADD CONSTRAINT antinuke_threshold_pkey PRIMARY KEY (guild_id);


--
-- Name: antinuke_whitelist antinuke_whitelist_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.antinuke_whitelist
    ADD CONSTRAINT antinuke_whitelist_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: antiraid antiraid_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.antiraid
    ADD CONSTRAINT antiraid_pkey PRIMARY KEY (guild_id);


--
-- Name: antisr_guilds antisr_guilds_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.antisr_guilds
    ADD CONSTRAINT antisr_guilds_pkey PRIMARY KEY (guild_id);


--
-- Name: antisr_ignores antisr_ignores_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.antisr_ignores
    ADD CONSTRAINT antisr_ignores_pkey PRIMARY KEY (guild_id, target_id);


--
-- Name: antisr_users antisr_users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.antisr_users
    ADD CONSTRAINT antisr_users_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: auth auth_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth
    ADD CONSTRAINT auth_pkey PRIMARY KEY (guild_id);


--
-- Name: auto_reactions auto_reactions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auto_reactions
    ADD CONSTRAINT auto_reactions_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: auto_responses auto_responses_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auto_responses
    ADD CONSTRAINT auto_responses_pkey PRIMARY KEY (guild_id, trigger);


--
-- Name: auto_responses auto_responses_trigger_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auto_responses
    ADD CONSTRAINT auto_responses_trigger_key UNIQUE (trigger);


--
-- Name: auto_roles auto_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auto_roles
    ADD CONSTRAINT auto_roles_pkey PRIMARY KEY (guild_id, role_id);


--
-- Name: auto_transcribe auto_transcribe_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auto_transcribe
    ADD CONSTRAINT auto_transcribe_pkey PRIMARY KEY (guild_id);


--
-- Name: autobanner_channels autobanner_channels_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.autobanner_channels
    ADD CONSTRAINT autobanner_channels_pkey PRIMARY KEY (guild_id, channel_id);


--
-- Name: automod automod_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.automod
    ADD CONSTRAINT automod_pkey PRIMARY KEY (guild_id);


--
-- Name: automod_timeout automod_timeout_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.automod_timeout
    ADD CONSTRAINT automod_timeout_pkey PRIMARY KEY (guild_id);


--
-- Name: autoname_channels autoname_channels_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.autoname_channels
    ADD CONSTRAINT autoname_channels_pkey PRIMARY KEY (guild_id, channel_id);


--
-- Name: autopfp_channels autopfp_channels_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.autopfp_channels
    ADD CONSTRAINT autopfp_channels_pkey PRIMARY KEY (guild_id, channel_id);


--
-- Name: autopfp autopfp_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.autopfp
    ADD CONSTRAINT autopfp_pkey PRIMARY KEY (guild_id, channel_id);


--
-- Name: autoreact_event autoreact_event_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.autoreact_event
    ADD CONSTRAINT autoreact_event_pkey PRIMARY KEY (guild_id, event, reaction);


--
-- Name: autoreact autoreact_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.autoreact
    ADD CONSTRAINT autoreact_pkey PRIMARY KEY (guild_id, keyword, reaction);


--
-- Name: autoresponder autoresponder_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.autoresponder
    ADD CONSTRAINT autoresponder_pkey PRIMARY KEY (guild_id, trig);


--
-- Name: autovanity_channels autovanity_channels_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.autovanity_channels
    ADD CONSTRAINT autovanity_channels_pkey PRIMARY KEY (guild_id, channel_id);


--
-- Name: birthday birthday_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.birthday
    ADD CONSTRAINT birthday_pkey PRIMARY KEY (user_id);


--
-- Name: birthdays birthdays_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.birthdays
    ADD CONSTRAINT birthdays_pkey PRIMARY KEY (user_id);


--
-- Name: blacklist blacklist_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.blacklist
    ADD CONSTRAINT blacklist_pkey PRIMARY KEY (user_id);


--
-- Name: blacklisted_deathinstance blacklisted_deathinstance_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.blacklisted_deathinstance
    ADD CONSTRAINT blacklisted_deathinstance_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: blacklisted blacklisted_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.blacklisted
    ADD CONSTRAINT blacklisted_pkey PRIMARY KEY (object_id, object_type);


--
-- Name: blacklisted_users blacklisted_users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.blacklisted_users
    ADD CONSTRAINT blacklisted_users_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: blunt blunt_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.blunt
    ADD CONSTRAINT blunt_pkey PRIMARY KEY (guild_id);


--
-- Name: blunt_state blunt_state_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.blunt_state
    ADD CONSTRAINT blunt_state_pkey PRIMARY KEY (guild_id);


--
-- Name: blunt_hits blunt_unique; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.blunt_hits
    ADD CONSTRAINT blunt_unique UNIQUE (user_id);


--
-- Name: boost_channels boost_channels_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.boost_channels
    ADD CONSTRAINT boost_channels_pkey PRIMARY KEY (guild_id, channel_id);


--
-- Name: boosters_lost boosters_lost_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.boosters_lost
    ADD CONSTRAINT boosters_lost_pkey PRIMARY KEY (user_id, guild_id);


--
-- Name: boosters boosters_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.boosters
    ADD CONSTRAINT boosters_pkey PRIMARY KEY (user_id);


--
-- Name: br_base br_base_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.br_base
    ADD CONSTRAINT br_base_pkey PRIMARY KEY (guild_id);


--
-- Name: captcha_settings captcha_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.captcha_settings
    ADD CONSTRAINT captcha_settings_pkey PRIMARY KEY (guild_id);


--
-- Name: captcha_verification captcha_verification_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.captcha_verification
    ADD CONSTRAINT captcha_verification_pkey PRIMARY KEY (guild_id);


--
-- Name: captcha_verification captcha_verification_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.captcha_verification
    ADD CONSTRAINT captcha_verification_user_id_key UNIQUE (user_id);


--
-- Name: captcha_verified captcha_verified_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.captcha_verified
    ADD CONSTRAINT captcha_verified_pkey PRIMARY KEY (guild_id);


--
-- Name: card_messages card_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.card_messages
    ADD CONSTRAINT card_messages_pkey PRIMARY KEY (user_id);


--
-- Name: cards_messages cards_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cards_messages
    ADD CONSTRAINT cards_messages_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: channelban channelban_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.channelban
    ADD CONSTRAINT channelban_pkey PRIMARY KEY (guild_id);


--
-- Name: chatfilter chatfilter_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chatfilter
    ADD CONSTRAINT chatfilter_pkey PRIMARY KEY (word, guild);


--
-- Name: cmderror cmderror_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cmderror
    ADD CONSTRAINT cmderror_pkey PRIMARY KEY (code);


--
-- Name: command_restriction command_restriction_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.command_restriction
    ADD CONSTRAINT command_restriction_pkey PRIMARY KEY (guild_id, command_name, role_id);


--
-- Name: command_usage command_usage_guild_id_user_id_command_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.command_usage
    ADD CONSTRAINT command_usage_guild_id_user_id_command_name_key UNIQUE (guild_id, user_id, command_name);


--
-- Name: companies companies_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.companies
    ADD CONSTRAINT companies_pkey PRIMARY KEY (user_id);


--
-- Name: confess_members confess_members_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.confess_members
    ADD CONSTRAINT confess_members_pkey PRIMARY KEY (guild_id, user_id, confession);


--
-- Name: confess_mute confess_mute_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.confess_mute
    ADD CONSTRAINT confess_mute_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: confess confess_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.confess
    ADD CONSTRAINT confess_pkey PRIMARY KEY (guild_id);


--
-- Name: confession_channels confession_channels_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.confession_channels
    ADD CONSTRAINT confession_channels_pkey PRIMARY KEY (guild_id, channel_id);


--
-- Name: disabled_commands conflict_issues42; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.disabled_commands
    ADD CONSTRAINT conflict_issues42 UNIQUE (guild_id, command);


--
-- Name: context context_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.context
    ADD CONSTRAINT context_pkey PRIMARY KEY (guild_id);


--
-- Name: counter_channels counter_channels_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.counter_channels
    ADD CONSTRAINT counter_channels_pkey PRIMARY KEY (channel_id);


--
-- Name: diary diary_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.diary
    ADD CONSTRAINT diary_pkey PRIMARY KEY (user_id, date);


--
-- Name: donators donators_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.donators
    ADD CONSTRAINT donators_pkey PRIMARY KEY (user_id);


--
-- Name: earnings earnings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.earnings
    ADD CONSTRAINT earnings_pkey PRIMARY KEY (user_id);


--
-- Name: economy economy_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.economy
    ADD CONSTRAINT economy_pkey PRIMARY KEY (user_id);


--
-- Name: ended_giveaways ended_giveaways_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ended_giveaways
    ADD CONSTRAINT ended_giveaways_pkey PRIMARY KEY (guild_id, message_id);


--
-- Name: fakeperms fakeperms_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fakeperms
    ADD CONSTRAINT fakeperms_pkey PRIMARY KEY (guild_id, role_id);


--
-- Name: filter_event filter_event_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.filter_event
    ADD CONSTRAINT filter_event_pkey PRIMARY KEY (guild_id, event);


--
-- Name: filter filter_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.filter
    ADD CONSTRAINT filter_pkey PRIMARY KEY (guild_id, keyword);


--
-- Name: filter_setup filter_setup_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.filter_setup
    ADD CONSTRAINT filter_setup_pkey PRIMARY KEY (guild_id);


--
-- Name: filter_snipe filter_snipe_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.filter_snipe
    ADD CONSTRAINT filter_snipe_pkey PRIMARY KEY (guild_id);


--
-- Name: filter_whitelist filter_whitelist_guild_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.filter_whitelist
    ADD CONSTRAINT filter_whitelist_guild_id_user_id_key UNIQUE (guild_id, user_id);


--
-- Name: forcenick forcenick_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forcenick
    ADD CONSTRAINT forcenick_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: freaky freaky_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.freaky
    ADD CONSTRAINT freaky_pkey PRIMARY KEY (user_id, target_id);


--
-- Name: gang_logs gang_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_logs
    ADD CONSTRAINT gang_logs_pkey PRIMARY KEY (id);


--
-- Name: gang_members gang_members_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_members
    ADD CONSTRAINT gang_members_pkey PRIMARY KEY (user_id, gang_name);


--
-- Name: gangs gangs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gangs
    ADD CONSTRAINT gangs_pkey PRIMARY KEY (gang_name);


--
-- Name: giveaway_blacklist giveaway_blacklist_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.giveaway_blacklist
    ADD CONSTRAINT giveaway_blacklist_pkey PRIMARY KEY (guild_id, role_id);


--
-- Name: giveaway_config giveaway_config_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.giveaway_config
    ADD CONSTRAINT giveaway_config_pkey PRIMARY KEY (guild_id);


--
-- Name: giveaway_entries giveaway_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.giveaway_entries
    ADD CONSTRAINT giveaway_entries_pkey PRIMARY KEY (guild_id, message_id, user_id);


--
-- Name: giveaway_settings giveaway_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.giveaway_settings
    ADD CONSTRAINT giveaway_settings_pkey PRIMARY KEY (guild_id, role_id);


--
-- Name: giveaway_templates giveaway_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.giveaway_templates
    ADD CONSTRAINT giveaway_templates_pkey PRIMARY KEY (guild_id);


--
-- Name: globalbans globalbans_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.globalbans
    ADD CONSTRAINT globalbans_pkey PRIMARY KEY (user_id);


--
-- Name: goodbye_channels goodbye_channels_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goodbye_channels
    ADD CONSTRAINT goodbye_channels_pkey PRIMARY KEY (guild_id, channel_id);


--
-- Name: graph_color graph_color_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.graph_color
    ADD CONSTRAINT graph_color_pkey PRIMARY KEY (user_id);


--
-- Name: guild_invites guild_invites_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.guild_invites
    ADD CONSTRAINT guild_invites_pkey PRIMARY KEY (guild_id);


--
-- Name: guild_notifications guild_notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.guild_notifications
    ADD CONSTRAINT guild_notifications_pkey PRIMARY KEY (guild_id);


--
-- Name: guild_settings guild_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.guild_settings
    ADD CONSTRAINT guild_settings_pkey PRIMARY KEY (guild_id);


--
-- Name: guilds guilds_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.guilds
    ADD CONSTRAINT guilds_pkey PRIMARY KEY (guild_id);


--
-- Name: guilds_stats guilds_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.guilds_stats
    ADD CONSTRAINT guilds_stats_pkey PRIMARY KEY (guild_id);


--
-- Name: gw gw_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gw
    ADD CONSTRAINT gw_pkey PRIMARY KEY (guild_id, message_id);


--
-- Name: highlight highlight_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.highlight
    ADD CONSTRAINT highlight_pkey PRIMARY KEY (user_id, word);


--
-- Name: hunted_animals hunted_animals_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.hunted_animals
    ADD CONSTRAINT hunted_animals_pkey PRIMARY KEY (user_id, animal_name);


--
-- Name: hunters hunters_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.hunters
    ADD CONSTRAINT hunters_pkey PRIMARY KEY (user_id);


--
-- Name: imageonly imageonly_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.imageonly
    ADD CONSTRAINT imageonly_pkey PRIMARY KEY (channel_id);


--
-- Name: instance_whitelist instance_whitelist_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.instance_whitelist
    ADD CONSTRAINT instance_whitelist_pkey PRIMARY KEY (user_id);


--
-- Name: instances instances_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.instances
    ADD CONSTRAINT instances_pkey PRIMARY KEY (user_id);


--
-- Name: interactions interactions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.interactions
    ADD CONSTRAINT interactions_pkey PRIMARY KEY (user1_id, user2_id, interaction);


--
-- Name: invoke invoke_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.invoke
    ADD CONSTRAINT invoke_pkey PRIMARY KEY (guild_id, cmd);


--
-- Name: jail_config jail_config_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.jail_config
    ADD CONSTRAINT jail_config_pkey PRIMARY KEY (guild_id);


--
-- Name: jailed jailed_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.jailed
    ADD CONSTRAINT jailed_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: join_dm_settings join_dm_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.join_dm_settings
    ADD CONSTRAINT join_dm_settings_pkey PRIMARY KEY (guild_id);


--
-- Name: labs labs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.labs
    ADD CONSTRAINT labs_pkey PRIMARY KEY (user_id);


--
-- Name: lastfm_commands lastfm_commands_command_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lastfm_commands
    ADD CONSTRAINT lastfm_commands_command_key UNIQUE (command);


--
-- Name: lastfm_commands lastfm_commands_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lastfm_commands
    ADD CONSTRAINT lastfm_commands_pkey PRIMARY KEY (command, user_id);


--
-- Name: lastfm_commands lastfm_commands_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lastfm_commands
    ADD CONSTRAINT lastfm_commands_user_id_key UNIQUE (user_id);


--
-- Name: lastfm_crowns lastfm_crowns_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lastfm_crowns
    ADD CONSTRAINT lastfm_crowns_pkey PRIMARY KEY (guild_id, artist, user_id);


--
-- Name: lastfm_embeds lastfm_embeds_embed_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lastfm_embeds
    ADD CONSTRAINT lastfm_embeds_embed_code_key UNIQUE (embed_code);


--
-- Name: lastfm_embeds lastfm_embeds_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lastfm_embeds
    ADD CONSTRAINT lastfm_embeds_pkey PRIMARY KEY (user_id, embed_code);


--
-- Name: lastfm_embeds lastfm_embeds_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lastfm_embeds
    ADD CONSTRAINT lastfm_embeds_user_id_key UNIQUE (user_id);


--
-- Name: lastfm_likes lastfm_likes_user_id_track_artist_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lastfm_likes
    ADD CONSTRAINT lastfm_likes_user_id_track_artist_key UNIQUE (user_id, track, artist);


--
-- Name: lastfm lastfm_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lastfm
    ADD CONSTRAINT lastfm_user_id_key UNIQUE (user_id);


--
-- Name: lastfm_crowns lastfm_wk_al; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lastfm_crowns
    ADD CONSTRAINT lastfm_wk_al UNIQUE (album);


--
-- Name: lf_reactions lf_reactions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lf_reactions
    ADD CONSTRAINT lf_reactions_pkey PRIMARY KEY (user_id);


--
-- Name: lock_role lock_role_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lock_role
    ADD CONSTRAINT lock_role_pkey PRIMARY KEY (guild_id);


--
-- Name: logs logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.logs
    ADD CONSTRAINT logs_pkey PRIMARY KEY (id);


--
-- Name: lottery lottery_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lottery
    ADD CONSTRAINT lottery_pkey PRIMARY KEY (id);


--
-- Name: marriages marriages_user1_id_user2_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.marriages
    ADD CONSTRAINT marriages_user1_id_user2_id_key UNIQUE (user1_id, user2_id);


--
-- Name: mentions mentions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mentions
    ADD CONSTRAINT mentions_pkey PRIMARY KEY (id);


--
-- Name: message_activity message_activity_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.message_activity
    ADD CONSTRAINT message_activity_pkey PRIMARY KEY (user_id, guild_id);


--
-- Name: message_count message_count_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.message_count
    ADD CONSTRAINT message_count_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: mod_mail mod_mail_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_mail
    ADD CONSTRAINT mod_mail_pkey PRIMARY KEY (guild_id);


--
-- Name: moderation_channel moderation_channel_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.moderation_channel
    ADD CONSTRAINT moderation_channel_pkey PRIMARY KEY (guild_id);


--
-- Name: moderation_events moderation_events_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.moderation_events
    ADD CONSTRAINT moderation_events_pkey PRIMARY KEY (id);


--
-- Name: moderation_logs moderation_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.moderation_logs
    ADD CONSTRAINT moderation_logs_pkey PRIMARY KEY (id);


--
-- Name: moderation_statistics moderation_statistics_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.moderation_statistics
    ADD CONSTRAINT moderation_statistics_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: modlog_queue modlog_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.modlog_queue
    ADD CONSTRAINT modlog_queue_pkey PRIMARY KEY (id);


--
-- Name: names names_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.names
    ADD CONSTRAINT names_pkey PRIMARY KEY (user_id, username, ts);


--
-- Name: niggertalk niggertalk_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.niggertalk
    ADD CONSTRAINT niggertalk_pkey PRIMARY KEY (guild_id, channel_id, user_id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (guild_id);


--
-- Name: nsfw_stats nsfw_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.nsfw_stats
    ADD CONSTRAINT nsfw_stats_pkey PRIMARY KEY (user_id, target_id);


--
-- Name: nword nword_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.nword
    ADD CONSTRAINT nword_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: offensive offensive_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.offensive
    ADD CONSTRAINT offensive_pkey PRIMARY KEY (user_id);


--
-- Name: offensive_words offensive_words_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.offensive_words
    ADD CONSTRAINT offensive_words_pkey PRIMARY KEY (user_id);


--
-- Name: opened_ticket_topics opened_ticket_topics_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opened_ticket_topics
    ADD CONSTRAINT opened_ticket_topics_pkey PRIMARY KEY (guild_id, channel_id);


--
-- Name: opened_tickets opened_tickets_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opened_tickets
    ADD CONSTRAINT opened_tickets_pkey PRIMARY KEY (channel_id);


--
-- Name: paginator paginator_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.paginator
    ADD CONSTRAINT paginator_pkey PRIMARY KEY (guild_id, name);


--
-- Name: pfps pfps_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pfps
    ADD CONSTRAINT pfps_pkey PRIMARY KEY (guild_id, channel_id);


--
-- Name: pingonjoin pingonjoin_guild_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pingonjoin
    ADD CONSTRAINT pingonjoin_guild_id_key UNIQUE (guild_id);


--
-- Name: poj_channels poj_channels_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.poj_channels
    ADD CONSTRAINT poj_channels_pkey PRIMARY KEY (guild_id, channel_id);


--
-- Name: prefixes prefixes_guild_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.prefixes
    ADD CONSTRAINT prefixes_guild_id_key UNIQUE (guild_id);


--
-- Name: premium_users premium_users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.premium_users
    ADD CONSTRAINT premium_users_pkey PRIMARY KEY (user_id);


--
-- Name: premiumrole premiumrole_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.premiumrole
    ADD CONSTRAINT premiumrole_pkey PRIMARY KEY (guild_id);


--
-- Name: protected protected_guild_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.protected
    ADD CONSTRAINT protected_guild_id_key UNIQUE (guild_id);


--
-- Name: protected_roles protected_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.protected_roles
    ADD CONSTRAINT protected_roles_pkey PRIMARY KEY (guild_id, role_id);


--
-- Name: reaction_triggers reaction_triggers_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reaction_triggers
    ADD CONSTRAINT reaction_triggers_pkey PRIMARY KEY (guild_id, trigger, reaction);


--
-- Name: reactionrole reactionrole_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reactionrole
    ADD CONSTRAINT reactionrole_pkey PRIMARY KEY (guild_id, channel_id, message_id, role_id, emoji);


--
-- Name: reminders reminders_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reminders
    ADD CONSTRAINT reminders_pkey PRIMARY KEY (user_id);


--
-- Name: report_channel report_channel_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.report_channel
    ADD CONSTRAINT report_channel_pkey PRIMARY KEY (guild_id);


--
-- Name: report_whitelist report_whitelist_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.report_whitelist
    ADD CONSTRAINT report_whitelist_pkey PRIMARY KEY (user_id);


--
-- Name: reskin_config reskin_config_guild_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reskin_config
    ADD CONSTRAINT reskin_config_guild_id_key UNIQUE (guild_id);


--
-- Name: reskin reskin_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reskin
    ADD CONSTRAINT reskin_user_id_key UNIQUE (user_id);


--
-- Name: revive revive_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.revive
    ADD CONSTRAINT revive_pkey PRIMARY KEY (guild_id);


--
-- Name: rolelock rolelock_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.rolelock
    ADD CONSTRAINT rolelock_pkey PRIMARY KEY (id);


--
-- Name: screentime screentime_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.screentime
    ADD CONSTRAINT screentime_pkey PRIMARY KEY (user_id);


--
-- Name: self_prefixes self_prefixes_guild_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.self_prefixes
    ADD CONSTRAINT self_prefixes_guild_id_key UNIQUE (guild_id);


--
-- Name: selfprefix selfprefix2_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.selfprefix
    ADD CONSTRAINT selfprefix2_pkey PRIMARY KEY (user_id);


--
-- Name: sp2 selfprefix_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sp2
    ADD CONSTRAINT selfprefix_pkey PRIMARY KEY (user_id, prefix);


--
-- Name: server_activity server_activity_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.server_activity
    ADD CONSTRAINT server_activity_pkey PRIMARY KEY (user_id, guild_id);


--
-- Name: server_settings server_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.server_settings
    ADD CONSTRAINT server_settings_pkey PRIMARY KEY (guild_id);


--
-- Name: starboard_entries starboard_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.starboard_entries
    ADD CONSTRAINT starboard_entries_pkey PRIMARY KEY (guild_id, starboard_message_id);


--
-- Name: starboard_ignored starboard_ignored_guild_id_channel_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.starboard_ignored
    ADD CONSTRAINT starboard_ignored_guild_id_channel_id_key UNIQUE (guild_id, channel_id);


--
-- Name: starboard_ignored starboard_ignored_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.starboard_ignored
    ADD CONSTRAINT starboard_ignored_pkey PRIMARY KEY (id);


--
-- Name: starboard starboard_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.starboard
    ADD CONSTRAINT starboard_pkey PRIMARY KEY (guild_id, emoji);


--
-- Name: steal_disabled steal_disabled_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.steal_disabled
    ADD CONSTRAINT steal_disabled_pkey PRIMARY KEY (guild_id);


--
-- Name: sticky_messages sticky_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sticky_messages
    ADD CONSTRAINT sticky_messages_pkey PRIMARY KEY (guild_id, channel_id);


--
-- Name: suggestions suggestions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.suggestions
    ADD CONSTRAINT suggestions_pkey PRIMARY KEY (message_id);


--
-- Name: supergamble_data supergamble_data_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.supergamble_data
    ADD CONSTRAINT supergamble_data_pkey PRIMARY KEY (user_id);


--
-- Name: system_messages system_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.system_messages
    ADD CONSTRAINT system_messages_pkey PRIMARY KEY (guild_id);


--
-- Name: terms_agreement terms_agreement_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.terms_agreement
    ADD CONSTRAINT terms_agreement_pkey PRIMARY KEY (user_id);


--
-- Name: text_level_settings text_level_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.text_level_settings
    ADD CONSTRAINT text_level_settings_pkey PRIMARY KEY (guild_id);


--
-- Name: text_levels text_levels_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.text_levels
    ADD CONSTRAINT text_levels_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: ticket_topic_categories ticket_topic_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_topic_categories
    ADD CONSTRAINT ticket_topic_categories_pkey PRIMARY KEY (guild_id, topic_name);


--
-- Name: ticket_topic_roles ticket_topic_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_topic_roles
    ADD CONSTRAINT ticket_topic_roles_pkey PRIMARY KEY (guild_id, topic_name, role_id);


--
-- Name: ticket_topics ticket_topics_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_topics
    ADD CONSTRAINT ticket_topics_pkey PRIMARY KEY (guild_id, name);


--
-- Name: tickets tickets_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_pkey PRIMARY KEY (guild_id);


--
-- Name: timezone timezone_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.timezone
    ADD CONSTRAINT timezone_pkey PRIMARY KEY (user_id);


--
-- Name: traceback traceback_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.traceback
    ADD CONSTRAINT traceback_pkey PRIMARY KEY (error_code);


--
-- Name: tracking_channels tracking_channels_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tracking_channels
    ADD CONSTRAINT tracking_channels_pkey PRIMARY KEY (guild_id);


--
-- Name: lastfm_crowns unique_guild_artist; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lastfm_crowns
    ADD CONSTRAINT unique_guild_artist UNIQUE (guild_id, artist);


--
-- Name: starboard_entries unique_starboard_entry; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.starboard_entries
    ADD CONSTRAINT unique_starboard_entry UNIQUE (guild_id, channel_id, message_id, emoji);


--
-- Name: inventory unique_user_item; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT unique_user_item UNIQUE (user_id, item);


--
-- Name: used_items unique_user_items; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.used_items
    ADD CONSTRAINT unique_user_items UNIQUE (user_id, item);


--
-- Name: user_fish user_fish_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_fish
    ADD CONSTRAINT user_fish_pkey PRIMARY KEY (user_id);


--
-- Name: user_levels user_levels_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_levels
    ADD CONSTRAINT user_levels_pkey PRIMARY KEY (user_id, guild_id);


--
-- Name: offensive user_unique; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.offensive
    ADD CONSTRAINT user_unique UNIQUE (user_id);


--
-- Name: usercard_messages usercard_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.usercard_messages
    ADD CONSTRAINT usercard_messages_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: username_changes username_changes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.username_changes
    ADD CONSTRAINT username_changes_pkey PRIMARY KEY (user_id);


--
-- Name: uwulock uwulock_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.uwulock
    ADD CONSTRAINT uwulock_pkey PRIMARY KEY (guild_id, user_id, channel_id);


--
-- Name: vanity vanity_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.vanity
    ADD CONSTRAINT vanity_pkey PRIMARY KEY (guild_id);


--
-- Name: vanity_roles vanity_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.vanity_roles
    ADD CONSTRAINT vanity_roles_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: vanity_status vanity_status_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.vanity_status
    ADD CONSTRAINT vanity_status_pkey PRIMARY KEY (guild_id);


--
-- Name: vape_flavors vape_flavors_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.vape_flavors
    ADD CONSTRAINT vape_flavors_pkey PRIMARY KEY (user_id);


--
-- Name: vape vape_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.vape
    ADD CONSTRAINT vape_pkey PRIMARY KEY (guild_id);


--
-- Name: vcbans vcbans_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.vcbans
    ADD CONSTRAINT vcbans_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: verified_users verified_users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.verified_users
    ADD CONSTRAINT verified_users_pkey PRIMARY KEY (user_id);


--
-- Name: vm_status vm_status_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.vm_status
    ADD CONSTRAINT vm_status_pkey PRIMARY KEY (user_id);


--
-- Name: voice_activity voice_activity_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.voice_activity
    ADD CONSTRAINT voice_activity_pkey PRIMARY KEY (user_id, guild_id);


--
-- Name: voice_levels voice_levels_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.voice_levels
    ADD CONSTRAINT voice_levels_pkey PRIMARY KEY (guild_id, user_id);


--
-- Name: voicetime_overall voicetime_overall_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.voicetime_overall
    ADD CONSTRAINT voicetime_overall_pkey PRIMARY KEY (user_id);


--
-- Name: warning_punishments warning_punishments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.warning_punishments
    ADD CONSTRAINT warning_punishments_pkey PRIMARY KEY (guild_id, threshold);


--
-- Name: warnings warnings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.warnings
    ADD CONSTRAINT warnings_pkey PRIMARY KEY (id);


--
-- Name: welcome_channels welcome_channels_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.welcome_channels
    ADD CONSTRAINT welcome_channels_pkey PRIMARY KEY (guild_id, channel_id);


--
-- Name: whitelist whitelist_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.whitelist
    ADD CONSTRAINT whitelist_pkey PRIMARY KEY (user_id);


--
-- Name: word_counts word_counts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.word_counts
    ADD CONSTRAINT word_counts_pkey PRIMARY KEY (guild_id, user_id, word);


--
-- Name: main main_pkey; Type: CONSTRAINT; Schema: reaction_roles; Owner: postgres
--

ALTER TABLE ONLY reaction_roles.main
    ADD CONSTRAINT main_pkey PRIMARY KEY (guild_id, message_id, role_id);


--
-- Name: fail fail_pkey; Type: CONSTRAINT; Schema: reskin; Owner: postgres
--

ALTER TABLE ONLY reskin.fail
    ADD CONSTRAINT fail_pkey PRIMARY KEY (user_id);


--
-- Name: main main_pkey; Type: CONSTRAINT; Schema: reskin; Owner: postgres
--

ALTER TABLE ONLY reskin.main
    ADD CONSTRAINT main_pkey PRIMARY KEY (user_id);


--
-- Name: server server_pkey; Type: CONSTRAINT; Schema: reskin; Owner: postgres
--

ALTER TABLE ONLY reskin.server
    ADD CONSTRAINT server_pkey PRIMARY KEY (guild_id);


--
-- Name: success success_pkey; Type: CONSTRAINT; Schema: reskin; Owner: postgres
--

ALTER TABLE ONLY reskin.success
    ADD CONSTRAINT success_pkey PRIMARY KEY (user_id);


--
-- Name: main main_pkey; Type: CONSTRAINT; Schema: starboard; Owner: postgres
--

ALTER TABLE ONLY starboard.main
    ADD CONSTRAINT main_pkey PRIMARY KEY (guild_id, emoji);


--
-- Name: outages outages_pkey; Type: CONSTRAINT; Schema: status; Owner: postgres
--

ALTER TABLE ONLY status.outages
    ADD CONSTRAINT outages_pkey PRIMARY KEY (id);


--
-- Name: active_streams active_streams_pkey; Type: CONSTRAINT; Schema: twitch; Owner: postgres
--

ALTER TABLE ONLY twitch.active_streams
    ADD CONSTRAINT active_streams_pkey PRIMARY KEY (stream_id);


--
-- Name: custom_messages custom_messages_pkey; Type: CONSTRAINT; Schema: twitch; Owner: postgres
--

ALTER TABLE ONLY twitch.custom_messages
    ADD CONSTRAINT custom_messages_pkey PRIMARY KEY (guild_id, channel_id);


--
-- Name: subscriptions subscriptions_pkey; Type: CONSTRAINT; Schema: twitch; Owner: postgres
--

ALTER TABLE ONLY twitch.subscriptions
    ADD CONSTRAINT subscriptions_pkey PRIMARY KEY (username, channel_id);


--
-- Name: activity_log activity_log_user_id_guild_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.activity_log
    ADD CONSTRAINT activity_log_user_id_guild_id_fkey FOREIGN KEY (user_id, guild_id) REFERENCES public.user_levels(user_id, guild_id);


--
-- Name: earnings earnings_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.earnings
    ADD CONSTRAINT earnings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.economy(user_id) ON DELETE CASCADE;


--
-- Name: gang_members gang_members_gang_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_members
    ADD CONSTRAINT gang_members_gang_name_fkey FOREIGN KEY (gang_name) REFERENCES public.gangs(gang_name) ON DELETE CASCADE;


--
-- Name: opened_tickets opened_tickets_guild_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opened_tickets
    ADD CONSTRAINT opened_tickets_guild_id_fkey FOREIGN KEY (guild_id) REFERENCES public.tickets(guild_id) ON DELETE CASCADE;


--
-- Name: ticket_topics ticket_topics_guild_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_topics
    ADD CONSTRAINT ticket_topics_guild_id_fkey FOREIGN KEY (guild_id) REFERENCES public.tickets(guild_id) ON DELETE CASCADE;


--
-- Name: user_levels user_levels_guild_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_levels
    ADD CONSTRAINT user_levels_guild_id_fkey FOREIGN KEY (guild_id) REFERENCES public.guilds(guild_id);


--
-- PostgreSQL database dump complete
--

