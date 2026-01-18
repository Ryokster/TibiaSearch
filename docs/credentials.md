# Credential Storage (Windows)

This project stores credentials in the Windows Credential Manager as Generic Credentials.
Windows manages these entries; they are encrypted with DPAPI and tied to the current Windows user.

## What is stored
- Target (namespace string)
- Username
- Password (stored by Windows, encrypted via DPAPI)

## Where to view them
Open **Credential Manager** → **Windows Credentials** → **Generic Credentials**.

## Target naming recommendation
Use a stable namespace to avoid collisions and to support multiple accounts:
- `com.tibiasearch.tibia.login.main`
- `com.meinprojekt.tibia.login.alt01`

## Migration note
DPAPI binds credentials to the Windows user profile. If you move to a new PC or Windows user,
recreate the credentials on that machine.
