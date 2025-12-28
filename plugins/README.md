# Plugins Directory

This directory contains plugin modules that extend the sales-agent platform.

## Plugin Architecture

Plugins are Python modules that register with the main application to add functionality.

## Creating a Plugin

1. Create a new directory for your plugin
2. Add an `__init__.py` with registration logic
3. Import and register in the main application

## Available Plugins

(None currently active - directory reserved for future extensions)

## Plugin Guidelines

- Keep plugins self-contained
- Document dependencies in plugin README
- Follow the service layer pattern (<200 lines per file)
