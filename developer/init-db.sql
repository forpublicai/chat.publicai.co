-- Create LiteLLM user and database
CREATE USER llmproxy WITH PASSWORD 'password';
CREATE DATABASE litellm OWNER llmproxy;

-- Create OpenWebUI user and database
CREATE USER openwebui WITH PASSWORD 'password';
CREATE DATABASE openwebui OWNER openwebui;
