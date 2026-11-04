# REST API Design Guide

A language-agnostic, practical guide to predictable REST API design, with examples for endpoint naming, pagination, filtering, sorting, and error handling.

## View the guide

The published guide is available at [https://balasurjeeth.github.io/rest-api-design-guide/](https://balasurjeeth.github.io/rest-api-design-guide/).

## Deploy

The site is plain static HTML and CSS in `site/`. GitHub Actions publishes it to GitHub Pages whenever changes are pushed to `main` and can also be run manually from the Actions tab. In the repository settings, set **Pages → Build and deployment → Source** to **GitHub Actions**.

## Contents

- Resource-oriented endpoint naming conventions and HTTP method semantics
- Pagination guidance for cursor- and offset-based APIs
- Query parameter patterns for filtering and sorting
- RFC 9457 Problem Details error shape
- Common HTTP status codes
