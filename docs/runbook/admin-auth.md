# Admin Authentication

Public Newsletter reading does not require login.

Admin login remains required because admin screens can change local Newsletter data:

- Import / Sync
- Newsletter creation
- Newsletter updates
- soft delete / inactive state changes
- thumbnail upload
- category and tag mutations

Development credentials are read from `backend/.env`:

```text
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me
```

Do not remove authentication from `/admin/*` routes unless all mutation and sync functionality is removed or moved behind another trust boundary.
