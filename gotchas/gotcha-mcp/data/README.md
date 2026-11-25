Placeholder — this directory becomes the `gotcha-db` git submodule once both repos are
pushed to GitHub. Until then, the DB content lives at `../../gotcha-db/`.

To wire (from a native shell, per this repo's FUSE-mount git quirks):

    cd gotcha-mcp
    git submodule add https://github.com/rsperry79/gotcha-db data
