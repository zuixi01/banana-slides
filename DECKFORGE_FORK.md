# Deckforge Banana Slides Fork

This application is based on [Anionex/banana-slides](https://github.com/Anionex/banana-slides), pinned initially to commit `828bf6dfa535083b4fa6f5bed097655847fe26e5`.

The upstream project is licensed under the GNU Affero General Public License v3.0. The original `LICENSE`, copyright notices, and project history are retained. Deckforge-specific changes are developed on the `migration/deckforge-core` branch.

## Migration policy

- The legacy Deckforge application remains outside this repository during migration.
- Secrets and runtime data must never be committed.
- Upstream changes are fetched from the `upstream` remote and integrated deliberately.
- Production releases must use immutable Git SHA or digest-based images.
