"""`python -m agency.entrypoints.server`: the same as `agency-server`."""

from agency.entrypoints.server.serve import main

raise SystemExit(main())
