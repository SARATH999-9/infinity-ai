# INFINITY AI

**An AI-powered web assistant for conversations, media creation, music
discovery, and productivity.*

Infinity AI is a web application built around a FastAPI backend and a
browser-based frontend. It brings AI chat and configurable media
integrations into one interface, with account authentication, usage
limits, and an optional Pro subscription flow.

> **Documentation accuracy:** This README describes the project
> capabilities and configuration reported for this repository. Some
> features depend on provider credentials, deployment environment
> variables, account status, and plan limits. A feature being documented
> does not guarantee that it is currently enabled or working in the
> deployed production environment. Verify the live deployment before
> advertising a feature as available

------------------------------------------------------------------------

## Table of contents

1.  [Highlights](#highlights)
2.  [Features](#features)
3.  [Free and Pro plans](#free-and-pro-plans)
4.  [Technology stack](#technology-stack)
5.  [How the application works](#how-the-application-works)
6.  [AI providers and integrations](#ai-providers-and-integrations)
7.  [Local setup](#local-setup)
8.  [Environment configuration](#environment-configuration)
9.  [Run the application](#run-the-application)
10. [Deployment](#deployment)
11. [Security practices](#security-practices)
12. [Troubleshooting](#troubleshooting)
13. [Testing checklist](#testing-checklist)
14. [Project status and verification](#project-status-and-verification)

------------------------------------------------------------------------

## Highlights

-   AI chat with streaming responses, subject to the configured AI
    provider.
-   Account registration and sign-in options.
-   Conversation history and saved conversations.
-   Image and file input for supported AI workflows.
-   Configurable image and video generation integrations.
-   YouTube song search and embedded-player workflow.
-   Daily usage limits for Free and Pro plans.
-   Pro upgrade presentation and Razorpay checkout integration.
-   Responsive black-and-gold application interface.
-   FastAPI backend suitable for deployment on a hosting platform such
    as Render.

## Features

### 1. AI chat assistant

The chat experience is designed to support:

-   Natural-language questions and answers.
-   Streaming responses where supported by the selected provider.
-   General-purpose assistance, explanations, and content generation.
-   Multiple AI provider configurations.
-   Conversation history and saved conversations.
-   Deep Thinking mode where enabled by the application configuration
    and provider.
-   User-specific chat access when authentication is enabled.

The actual model, provider availability, response limits, and
capabilities depend on the server configuration.

### 2. Accounts and authentication

The project includes authentication-related functionality such as:

-   Email and password registration/sign-in.
-   Optional Google sign-in.
-   Token-based authentication.
-   Protected backend endpoints.
-   User-specific application data and conversation access.

Email delivery, OTP verification, and Google sign-in require their
respective credentials and provider configuration. Do not assume these
services are active merely because their UI is present.

### 3. Image generation

The application has an image-generation integration layer intended to
support:

-   Text-prompt-based image creation.
-   Configurable image-generation providers and models.
-   Provider selection or fallback where configured.
-   Displaying generated image results in the application.

Image generation requires a supported provider and valid credentials.
Available models, free allowances, output quality, and costs are
controlled by the provider and current configuration.

### 4. Video generation

The application includes a configurable video-generation workflow
intended to support:

-   Text-prompt-based video requests.
-   Configured external video-generation providers.
-   Provider-specific request and result handling.
-   Displaying or linking to generated video output.
-   Plan-based daily video allowances.

Possible integrations previously configured for this project include
Gemini Veo, Magic Hour, and Pollinations. Each integration must be
checked against the current code, API access, provider terms,
credentials, and billing requirements. A provider name in configuration
does not mean that the provider is currently available.

### 5. YouTube music and video search

The YouTube integration is designed for two related workflows:

**Song/audio request** 1. The user enters a song title or artist. 2. The
backend searches YouTube using the YouTube Data API. 3. The application
displays a matching embeddable YouTube player when a suitable result is
available. 4. The user starts playback using YouTube's player controls.

**Music-video request** 1. The user asks for a song's video or official
music video. 2. The application searches for a relevant YouTube result.
3. The application presents a link to open the video on YouTube.

Important notes:

-   A valid `YOUTUBE_API_KEY` is required on the backend.
-   Search results and embedding availability are determined by YouTube.
-   Some videos may be unavailable, region-restricted, age-restricted,
    or disallow embedding.
-   Playback follows YouTube's own player behavior, terms, ads, and
    availability.
-   The application should link to YouTube rather than download or
    extract copyrighted audio/video.

### 6. File, image, and voice input

Depending on the enabled frontend and backend routes, the application
may support:

-   Uploading files for AI-assisted processing.
-   Sending images with a prompt.
-   Asking questions about supported uploaded content.
-   Voice input.
-   Read-aloud or text-to-speech output.

Supported file formats, file-size limits, transcription providers, and
voice availability must be verified in the deployed configuration.

### 7. Conversation experience

The interface is designed to provide:

-   A chat-oriented workspace.
-   Conversation navigation and saved chats.
-   Streaming response presentation.
-   Media previews in supported workflows.
-   Usage-limit messages.
-   Upgrade-plan presentation when a configured limit is reached.

### 8. Daily usage limits

The backend is responsible for enforcing daily message and video limits.
The frontend can display usage information and upgrade prompts, but
frontend-only checks must not be treated as security enforcement.

The repository documentation has used the following example/default plan
values. The deployed environment may override them:

-   Free messages: 20 per day.
-   Pro messages: 200 per day.
-   Free videos: 0 per day.
-   Pro videos: 3 per day.

When a user reaches a configured limit, the application is intended to
explain that the allowance has been reached and present the Pro plan.
Exact message text and modal behavior should be verified in the current
frontend and backend.

### 9. Pro plan and payments

The documented example Pro offer is:

-   Price: **₹2**
-   Duration: **30 days**
-   Daily messages: **200**
-   Daily video allowance: **3**, if video generation is enabled
-   Additional features: Deep Thinking and Free-plan features, subject
    to current implementation

The application includes a Razorpay integration workflow intended to:

1.  Create a payment order on the backend.
2.  Open the Razorpay checkout interface.
3.  Receive the checkout result.
4.  Verify the payment signature on the backend.
5.  Activate the subscription only after successful server-side
    verification.

**Payment safety:** Use Razorpay test mode while developing. Never
activate a subscription based only on a browser callback. Real payments
require an eligible, activated merchant account, valid live credentials,
correct server configuration, and compliance with Razorpay's current
terms. Do not publish secret keys.

The ₹2 amount and 30-day duration are configuration-dependent. Confirm
the amount returned by the backend and shown in checkout before enabling
live payments.

------------------------------------------------------------------------

## Free and Pro plans

The following table reflects the documented example configuration, not a
guarantee of current production settings.

  -----------------------------------------------------------------------
  Capability                               Free                       Pro
  ------------------- ------------------------- -------------------------
  AI chat              Yes, subject to provider  Yes, subject to provider

  Daily messages                             20                       200

  Daily video                                 0                         3
  generation                                    

  Deep Thinking        Depends on configuration    Documented as included

  YouTube                  If API is configured      If API is configured
  search/player                                 

  Image generation                   Depends on                Depends on
                         provider/configuration    provider/configuration

  Conversation               Subject to account        Subject to account
  history                              features                  features

  Price                                    Free  ₹2 / 30 days (documented
                                                                 default)
  -----------------------------------------------------------------------

Plan values should be controlled by the backend. Keep the frontend plan
display synchronized with the backend configuration so that users are
not shown a price or allowance different from the values used to create
orders and enforce quotas.

------------------------------------------------------------------------

## Technology stack

The project is described as using the following technologies and
services. Confirm exact versions and dependencies in the repository's
current files before preparing a release.

  Technology/service      Purpose
  ----------------------- -----------------------------------------
  Python                  Backend application language
  FastAPI                 Backend web framework and API routes
  Uvicorn                 ASGI server used to run FastAPI
  HTML, CSS, JavaScript   Browser-based user interface
  Gemini API              AI model integration when configured
  Groq API                AI model integration when configured
  YouTube Data API v3     Song and video search
  Razorpay                Payment checkout and order verification
  Google OAuth            Optional Google sign-in
  Render                  Hosting/deployment platform

Other providers may be used for image and video generation. Check the
provider modules and environment configuration in the current source
before listing them as active integrations.

## How the application works

A simplified request flow:

1.  A user opens the web frontend.
2.  The frontend sends requests to the FastAPI backend.
3.  The backend validates authentication where required.
4.  The backend checks usage limits for quota-controlled actions.
5.  The backend routes the request to the configured AI or media
    provider.
6.  The provider response is returned to the frontend.
7.  The frontend displays the response, generated media, or relevant
    player/link.

For subscription checkout, the backend creates the order and verifies
the payment result before granting Pro access.

For YouTube search, the backend uses the YouTube Data API key and
returns suitable search results for the frontend to display.

## AI providers and integrations

Provider availability depends on API keys, model access, billing, rate
limits, and provider-side changes.

  -----------------------------------------------------------------------
  Integration             Purpose                 Configuration
  ----------------------- ----------------------- -----------------------
  Google Gemini           AI chat and supported   `GEMINI_API_KEY`
                          multimodal tasks        

  Groq                    AI chat models          `GROQ_API_KEY`

  YouTube Data API v3     Song/video search       `YOUTUBE_API_KEY`

  Razorpay                Pro checkout            `RAZORPAY_KEY_ID`,
                                                  `RAZORPAY_KEY_SECRET`

  Google OAuth            Google sign-in          OAuth client
                                                  configuration

  Video providers         Video generation        Provider-specific keys
                                                  and settings

  Image providers         Image generation        Provider-specific keys
                                                  and settings
  -----------------------------------------------------------------------

Do not assume that one API key grants access to every model or modality.
For example, video-generation access may require separate billing,
permissions, or a provider-specific API.

------------------------------------------------------------------------

## Local setup

### Requirements

-   Windows, macOS, or Linux.
-   Python version compatible with the project's `requirements.txt`.
-   Git.
-   A terminal such as PowerShell.
-   API credentials for the integrations you want to test.

### 1. Clone the repository

``` powershell
git clone https://github.com/SARATH999-9/infinity-ai.git
cd infinity-ai
```

### 2. Open the backend folder

``` powershell
cd backend
```

### 3. Create and activate a virtual environment

``` powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, review your local execution-policy
settings or activate the environment using the appropriate command for
your shell. Do not change machine-wide security settings unnecessarily.

### 4. Install dependencies

``` powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 5. Create the environment file

``` powershell
copy .env.example .env
notepad .env
```

Add the credentials and configuration required for the features you
intend to test. Keep `.env` private.

### 6. Start the backend

``` powershell
python -m uvicorn main:app --reload
```

Open the local application at:

-   Frontend/application: `http://localhost:8000`
-   API documentation, if enabled: `http://localhost:8000/docs`

The exact routes depend on the current FastAPI application.

------------------------------------------------------------------------

## Environment configuration

The following is an illustrative configuration template. Use the exact
variable names read by the current source code and `.env.example`;
remove variables for integrations you do not use.

``` env
# AI providers
GEMINI_API_KEY=
GROQ_API_KEY=

# YouTube Data API v3
YOUTUBE_API_KEY=

# Daily plan limits
FREE_DAILY_LIMIT=20
PRO_DAILY_LIMIT=200
FREE_VIDEO_LIMIT=0
PRO_VIDEO_LIMIT=3

# Pro subscription
PRO_PRICE_PAISE=200
PRO_DAYS=30

# Razorpay: use test credentials during development
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=

# Google sign-in and email/OTP settings
# Add the exact variable names required by the current application.

# Image/video providers
# Add provider-specific keys and settings only when required.
```

### Important configuration notes

-   `PRO_PRICE_PAISE=200` represents ₹2 because Razorpay order amounts
    are specified in paise for INR.
-   `PRO_DAYS=30` represents a 30-day subscription period if the
    application uses this variable.
-   The backend must be the source of truth for price and quota
    enforcement.
-   Set the same intended configuration in local development and
    hosting.
-   Never put private API secrets in frontend JavaScript or HTML.
-   Check the actual configuration parser before adding new variable
    names.

------------------------------------------------------------------------

## Deployment

The project has been deployed/planned for deployment using Render.

### Render deployment checklist

1.  Push the intended application code to the GitHub branch connected to
    Render.
2.  Confirm that Render is connected to the correct repository and
    branch.
3.  Set the correct service root directory and build/start commands for
    the repository layout.
4.  Add required environment variables in the Render service's
    Environment settings.
5.  Ensure the FastAPI server binds to `0.0.0.0` and the port supplied
    by the hosting platform.
6.  Review build logs and runtime logs for import, dependency,
    configuration, and startup errors.
7.  Open the Render-provided service URL and test the public
    application.
8.  Configure the custom domain and verify its DNS records.
9.  Re-test authentication, quotas, media integrations, and payment
    flows after deployment.

### Known deployment URLs

-   Custom domain: https://infinityai.mooo.com
-   Render service: https://infinity-ai-t4bq.onrender.com/

These URLs are included as project references. Their current
availability must be checked independently; their presence in this
README is not a claim that the deployment is online.

### Custom domain

If the Render URL works but the custom domain does not:

-   Check the domain's DNS records against Render's current
    custom-domain instructions.
-   Confirm the domain is added to the correct Render service.
-   Check DNS propagation and HTTPS certificate status.
-   Avoid changing DNS records based on guesses; use the values shown in
    the Render dashboard.

------------------------------------------------------------------------

## Security practices

-   Never commit `.env`, private keys, tokens, database files, or
    credentials.
-   If a secret has been committed or exposed, revoke or rotate it in
    the provider dashboard.
-   Keep API keys on the backend.
-   Restrict API keys to the required APIs and origins/IPs where
    supported.
-   Validate authentication and authorization on the backend.
-   Enforce daily quotas on the backend, not only in the browser.
-   Verify Razorpay payment signatures on the server.
-   Do not grant Pro access based only on a frontend success message.
-   Validate uploaded file types and sizes.
-   Avoid logging passwords, OTPs, payment secrets, or access tokens.
-   Use HTTPS in production.
-   Review provider terms and applicable copyright rules for
    user-generated and embedded media.

------------------------------------------------------------------------

## Troubleshooting

### Application does not start

-   Confirm that the terminal is inside the correct backend directory.
-   Activate the intended virtual environment.
-   Install dependencies from `requirements.txt`.
-   Check the traceback for missing modules or import-name conflicts.
-   Confirm that the Uvicorn module path matches the actual application
    file.

### Render reports that no port is open

-   Ensure the application binds to `0.0.0.0`.
-   Use the hosting platform's assigned port.
-   Check the Render start command and runtime logs.
-   Confirm that startup does not fail before the server begins
    listening.

### Website does not load on the custom domain

-   Test the Render URL separately.
-   Check custom-domain configuration and DNS records.
-   Check HTTPS certificate status.
-   Review Render logs and DNS resolution before changing application
    code.

### AI requests fail

-   Confirm the relevant API key is set in the hosting environment.
-   Check that the selected model is available to the account.
-   Review provider billing, quota, and rate-limit status.
-   Check backend logs for the provider's actual error response.

### YouTube search returns no results

-   Confirm `YOUTUBE_API_KEY` is configured on the backend.
-   Confirm the key has YouTube Data API v3 access.
-   Check API restrictions, quota, and backend logs.
-   Remember that not every YouTube video can be embedded.

### YouTube player does not play

-   Try another result.
-   Check whether the video allows embedding.
-   Check browser console/network errors and YouTube player messages.
-   Open the video on YouTube to check whether it is available there.

### Video generation is unavailable

-   Confirm that a video provider is configured.
-   Check that the selected provider key and model are valid.
-   Check provider access, billing, credits, and rate limits.
-   Confirm the plan's video quota is greater than zero.
-   Do not advertise video generation as active if the backend reports
    that no provider is available.

### Razorpay checkout fails

-   Confirm whether the application is using test or live keys.
-   Check merchant account activation and payment-product eligibility.
-   Confirm that the key ID and secret belong to the same mode.
-   Check backend order-creation and signature-verification logs.
-   Never switch to live payments until the merchant account and
    integration have been properly verified.

### Pro price differs between the plan page and checkout

-   Check the backend's configured price.
-   Check the frontend's displayed fallback price.
-   Ensure the plan display and order-creation endpoint use the same
    server-side amount.
-   Test the displayed amount in test mode before accepting real
    payments.

------------------------------------------------------------------------

## Testing checklist

Use this checklist after local setup or deployment. Test only with
accounts and services you are authorized to use.

-   [ ] Public homepage loads over HTTPS.
-   [ ] Registration and sign-in work.
-   [ ] Google sign-in works when configured.
-   [ ] Authenticated chat returns an AI response.
-   [ ] Streaming responses render correctly.
-   [ ] Conversations can be saved and reopened.
-   [ ] File and image input work for supported formats.
-   [ ] Voice input/read-aloud work when configured.
-   [ ] Image generation works with an enabled provider.
-   [ ] Video generation works with an enabled provider and eligible
    plan.
-   [ ] Free daily message quota is enforced by the backend.
-   [ ] Free-limit message and upgrade presentation appear correctly.
-   [ ] Pro plan price and duration match the backend configuration.
-   [ ] Pro daily message/video quotas are enforced correctly.
-   [ ] YouTube song search returns suitable results.
-   [ ] Embedded YouTube playback works for embeddable videos.
-   [ ] Video-song links open the intended YouTube page.
-   [ ] Razorpay test checkout opens without completing an unintended
    purchase.
-   [ ] Payment signature verification is enforced server-side.
-   [ ] Pro access is granted only after verified payment.
-   [ ] Custom domain and Render URL both resolve and load.

------------------------------------------------------------------------

## Project status and verification

This README documents the intended application scope and known
configuration. Before publishing a release, compare every feature
against the current source code and test it in the target environment.

Use clear status labels in project demonstrations:

-   **Implemented:** confirmed in the current source code.
-   **Configured:** required credentials/settings are present.
-   **Tested:** successfully exercised in the target environment.
-   **Unavailable:** provider, account, quota, or deployment prevents
    use.
-   **Not verified:** evidence is not yet available.

Do not describe a feature as production-ready solely because its UI,
route, or provider configuration exists.

## Repository

-   GitHub: https://github.com/SARATH999-9/infinity-ai
-   Custom domain: https://infinityai.mooo.com
-   Render: https://infinity-ai-t4bq.onrender.com/

------------------------------------------------------------------------

**INFINITY AI --- One workspace for AI assistance, media creation, and
music discovery.**
