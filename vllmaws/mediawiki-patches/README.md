# MediaWiki PSR-7 Compatibility Patches

## Overview
These patches fix PSR-7 StreamInterface compatibility issues in MediaWiki 1.43.6 that cause 500 errors when using the Visual Editor and other features.

## Issue
The Canasta image (MediaWiki 1.43.6) has stream classes that don't fully comply with PSR-7 `StreamInterface` return type declarations, causing PHP Fatal errors:
- `MWCallbackStream::write()` missing `: int` return type
- `StringStream` methods missing various return type declarations (`: void`, `: int`, `: bool`, `: string`, `: mixed`)

## Upstream Fix
These issues were fixed in upstream MediaWiki core:
- https://gerrit.wikimedia.org/r/c/mediawiki/core/+/1178975

However, Canasta has not yet released an updated image with these fixes.

## Patched Files
1. `includes/http/MWCallbackStream.php` - Added `: int` return type to `write()` method
2. `includes/Rest/StringStream.php` - Added proper return type declarations to all PSR-7 interface methods

## When to Remove
These patches can be removed once Canasta releases an updated image that includes the upstream MediaWiki fixes. You can check by:
1. Pulling the latest Canasta image
2. Temporarily removing these volume mounts from docker-compose.yml
3. Testing if the Visual Editor works without 500 errors

## Applied Date
December 22, 2025
