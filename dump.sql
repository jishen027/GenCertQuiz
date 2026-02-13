--
-- PostgreSQL database dump
--

\restrict rdr9kq37xXetPKDpAmu4Pc9no04vcJbAZni1752D5EzuDAgNepyFHoxvvVbEqVM

-- Dumped from database version 17.7 (Debian 17.7-3.pgdg12+1)
-- Dumped by pg_dump version 17.7 (Debian 17.7-3.pgdg12+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: knowledge_base; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.knowledge_base (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    content text NOT NULL,
    embedding public.vector(1536),
    metadata jsonb,
    source_type character varying(20),
    created_at timestamp with time zone DEFAULT now(),
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english'::regconfig, COALESCE(content, ''::text))) STORED,
    CONSTRAINT knowledge_base_source_type_check CHECK (((source_type)::text = ANY ((ARRAY['textbook'::character varying, 'question'::character varying, 'diagram'::character varying, 'exam_paper'::character varying])::text[])))
);


ALTER TABLE public.knowledge_base OWNER TO postgres;

--
-- Name: COLUMN knowledge_base.tsv; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.knowledge_base.tsv IS 'Text search vector for keyword-based retrieval (hybrid search)';


--
-- Name: style_profiles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.style_profiles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_filename character varying(255) NOT NULL,
    topic_keywords text[],
    profile jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.style_profiles OWNER TO postgres;

--
-- Name: TABLE style_profiles; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.style_profiles IS 'Cached style profiles extracted from exam papers for psychometrician agent';


--
-- Data for Name: knowledge_base; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.knowledge_base (id, content, embedding, metadata, source_type, created_at) FROM stdin;
\.


--
-- Data for Name: style_profiles; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.style_profiles (id, source_filename, topic_keywords, profile, created_at, updated_at) FROM stdin;
\.


--
-- Name: knowledge_base knowledge_base_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.knowledge_base
    ADD CONSTRAINT knowledge_base_pkey PRIMARY KEY (id);


--
-- Name: style_profiles style_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.style_profiles
    ADD CONSTRAINT style_profiles_pkey PRIMARY KEY (id);


--
-- Name: knowledge_base_created_at_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX knowledge_base_created_at_idx ON public.knowledge_base USING btree (created_at DESC);


--
-- Name: knowledge_base_embedding_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX knowledge_base_embedding_idx ON public.knowledge_base USING ivfflat (embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: knowledge_base_source_type_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX knowledge_base_source_type_idx ON public.knowledge_base USING btree (source_type);


--
-- Name: knowledge_base_tsv_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX knowledge_base_tsv_idx ON public.knowledge_base USING gin (tsv);


--
-- Name: style_profiles_source_filename_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX style_profiles_source_filename_idx ON public.style_profiles USING btree (source_filename);


--
-- Name: style_profiles_topic_keywords_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX style_profiles_topic_keywords_idx ON public.style_profiles USING gin (topic_keywords);


--
-- PostgreSQL database dump complete
--

\unrestrict rdr9kq37xXetPKDpAmu4Pc9no04vcJbAZni1752D5EzuDAgNepyFHoxvvVbEqVM

