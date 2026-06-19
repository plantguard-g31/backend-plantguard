# Main.py

** This is the main entry point of FastAPI. It:
- Create the FastAPI application instance
- Registers middleware (CORS, GZip, rate limiting)
- Mounts all API routers (auth, diagnosis, history, admin)
- Sets up error handlers, logging, and health endpoints
- Defines startip/shoutdown lifecycle events

In Simple, it is the 'Control Panel' of Our Backend - it wires together all the components (security, db, models, API endpoints) into a single running application.**

* CORE LOGIC & FLOW (Step-by-step) *
Step 1: Imports

What's happening:

|Import                  |        Purpose                    |       Why We Need It                                   |  
|------------------------|-----------------------------------|--------------------------------------------------------|
|FastAPI                 | Creates the application instance  | Core framework for building APIs                       |  
|RedirectResponse        | Handles HTTP redirects            | Used for root URL → /docs redirect                     |
|CORSMiddleware          | Enables cross-origin requests     | Allows Flutter mobile app to call backend              |                          
|GZipMiddleware          | Compresses HTTP responses         | Reduces bandwidth for rural farmers (60-80% savings)   |  
|logging                 | Records events/errors             | Audit trails, debugging, monitoring                    |  
|auth, diagnosis, history,admin | API route handlers         | Each file defines endpoints for a feature              |  
|register_error_handlers | Maps HTTP codes to farmer-friendly messages | Bilingual (EN/NE) error responses            |  
|rate_limit_middleware   | Prevents abuse/DoS attacks        | 10 requests/60s per user protection                    |

## Steps2: Logging Config
