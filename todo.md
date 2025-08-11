# Context

Redis stores strava_refresh_token and strava_access_token
.env contains STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET

# Todo

- Implement calling athlete activities for last N days 
  - $ http get "https://www.strava.com/api/v3/athlete/activities?before=&after=&page=&per_page=" "Authorization: Bearer [[token]]"
  - support loading multiple pages
- Add an API endpoint for last N days of workouts
  - Return model should be simplified and contain mostly only data a fitness/cycling coach and nutritionist would need. So for example kilojoules or average_watts is relevant. Or for another example map or photo_count is NOT relevant.
  - Mapping to the return model should be done in appropriate class, not in router. Think like a seasoned software developer.
- Support getting new access token based on refresh token

```
curl -X POST https://www.strava.com/api/v3/oauth/token \
  -d client_id=ReplaceWithClientID \
  -d client_secret=ReplaceWithClientSecret \
  -d grant_type=refresh_token \
  -d refresh_token=ReplaceWithRefreshToken

Response Parameters
access_token
string	The short-lived access token
expires_at
integer	The number of seconds since the epoch when the provided access token will expire
expires_in
integer	Seconds until the short-lived access token will expire
refresh_token
string	The refresh token for this user, to be used to get the next access token for this user. Please expect that this value can change anytime you retrieve a new access token. Once a new refresh token code has been returned, the older code will no longer work.
```
  - make sure proper TTL is set on the access token when saving back to Redis