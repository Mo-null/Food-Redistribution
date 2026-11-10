# Food Redistribution Platform – Frontend

A React single-page app for the [backend API](../backend/README.md). It covers all three roles:

- **Donor** posts, edits and cancels donations (with optional free-text quick fill), confirms pickups, reports failed pickups.
- **Recipient** answers match offers inside the 30-minute window, sees the exact pickup location only after accepting, and sees their own reliability score.
- **Coordinator** approves or rejects organizations, reviews and resolves reports, and runs matching on demand.

All roles also have notifications, a profile page, a password change form, and a "Report a problem" form for matches.

**Stack:** React 19 · React Router 7 · Vite 8 · plain CSS (no UI library). Fonts are bundled, so the app makes no third-party requests.

## Run it

Requires Node.js 20.19 or newer and the backend running (see the backend README).

```bash
cd frontend
npm install
cp .env.example .env     # Windows: copy .env.example .env
npm run dev              # http://localhost:5173
```

The backend allows `http://localhost:5173` by default (`CORS_ORIGINS`), so open the app on `localhost`, not `127.0.0.1`.

| Variable       | Default                 | Purpose                                          |
| -------------- | ----------------------- | ------------------------------------------------ |
| `VITE_API_URL` | `http://localhost:8000` | Base URL of the backend API. Read at build time. |

Other commands: `npm run build` (output in `dist/`), `npm run preview`, `npm run lint`, `npm run format`.

## How it maps to the API

| Screen             | Route                                                 | Endpoints used                                                                                                                                           |
| ------------------ | ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Sign in / register | `/login`, `/register`                                 | `POST /users/login`, `POST /users/register`, `GET /users/me`                                                                                             |
| Donations (donor)  | `/donations`, `/donations/new`, `/donations/:id/edit` | `GET /donations/mine`, `GET/POST/PATCH/DELETE /donations`, `POST /donations/parse`                                                                       |
| Pickups (donor)    | `/pickups`                                            | `GET /matches`, `POST /matches/{id}/confirm`, `POST /matches/{id}/reject`                                                                                |
| Offers (recipient) | `/offers`                                             | `GET /matches`, `POST /matches/{id}/accept`, `POST /matches/{id}/decline`                                                                                |
| Notifications      | `/notifications`                                      | `GET /notifications`, `POST /notifications/{id}/read`                                                                                                    |
| Profile            | `/profile`                                            | `GET/PATCH /users/me`, `POST /users/me/change-password`, `GET /reliability/{id}`                                                                         |
| Coordinator        | `/coordinator`                                        | `GET /users/pending-verifications`, `POST /users/{id}/verify`, `GET /disputes`, `POST /disputes/{id}/resolve`, `GET /matches/{id}`, `POST /matching/run` |
| Report a problem   | dialog on a match                                     | `POST /disputes`                                                                                                                                         |

The API calls the same thing a "match" for both sides. The interface calls it an **offer** for recipients and a **pickup** for donors.

## Behaviour worth knowing

- **Session:** the login token is kept in `localStorage`. When the API answers 401 (the token lasts 60 minutes), the app signs the user out and says so on the sign-in page.
- **Live data:** lists and notifications refresh every 30 seconds and when the tab regains focus. The offer countdown ticks every second.
- **Privacy rules from the backend are shown as they are:** recipients see an approximate area until they accept.
- **Organizations:** a pending or rejected organization sees a banner explaining what it cannot do yet, and the post button is disabled.
- **Validation:** forms check the same limits as the API (expiry within 14 days and in the future, coordinates, amounts, password length) and also show the API's own error text if it still rejects a request.
- **Expiry bar:** every donation and offer shows the time left before the food expires. It turns amber in the last two hours.

## Project layout

```
src/
  main.jsx, App.jsx        entry point and routes (role-protected)
  api.js                   all HTTP calls, error handling, token storage
  auth.jsx, toast.jsx      session and message providers
  notifications.jsx        shared notification list for the header badge and page
  hooks.js                 useFetch (with polling), useNow, useAction
  format.js                labels, dates, statuses
  components/              Layout, Dialog, ExpiryBar, LocationFields, shared UI
  pages/                   one file per screen
  styles.css               design tokens and all styles
```

## Deploying later

Run `npm run build` with `VITE_API_URL` pointing at the deployed API and serve `dist/` as static files. Because the app uses client-side routing, the host must send every path to `index.html`. On the backend, add the frontend's address to `CORS_ORIGINS`.
