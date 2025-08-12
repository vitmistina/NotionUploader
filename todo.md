# Todo

[] implement endpoint for Strava Webhooks
  - I will register the webhook by hand in Bruno
  - make sure, that the webhook is not part of the openapi documentation
  - make sure, that the authorization/security matches specs of Strava (may be inconsistent with rest of endpoints)
  - this app is hosted at https://notionuploader-groa.onrender.com
    - [] provide the payload for me in the bruno Request subscription request, using the VM environment
[] based on the webhook, download activity detail, minify or even gzip the json (should still read as utf8 string) and upload to notion database NOTION_WORKOUT_DATABASE_ID
  - Notion database has columns defined in ./examples/notion-strava-workouts-db.csv
  - Some metrics need to be calculated (HR drift, VO2MAX minutes), use splits_metric from ./examples/activity-detail-example.json
    - you will need some data from NOTION_ATHLETE_PROFILE_DATABASE_ID, which has columns as described in ./examples/notion-athlete-profile-db.csv
      - only take the top 1 queried page, when sorted by descending Date
[] prepare an output model, mapping and implementation, which will load database entries for last N days from NOTION_WORKOUT_DATABASE_ID and output for an LLM trainer/coach, who will use these data to assess my training plan compliance

# Strava Webhook doc
Strava
Developers
Webhook Events API


Webhooks Overview
Webhook subscriptions allow an application to subscribe to events that occur within Strava. These events are pushed to a callback designated by the subscription shortly after the events occur on Strava. Webhooks enable applications to receive real-time updates for supported objects, eliminating the need for polling.

We encourage all API applications to use our webhook events API.

Event Data
The Strava Webhook Events API supports webhook events for certain changes to athlete and activity objects. Specifically, webhook events are pushed when an athlete revokes access to an application, or when an activity is created, deleted, or one of the following activity fields are updated:

Title
Type
Privacy, requires an access token with activity:read_all scope
When one of these events occurs in Strava, a POST request is made to the callback url for each subscription to which the event pertains. The body of this POST request contains the object_type and aspect_type of the updated object in addition to an object_id, which is either an activity or athlete ID. If additional information about the object is required, an application must decide how or if it wants to fetch the most up-to-date data. For example, you may decide only to fetch new data for specific users, or after a certain number of activities have been uploaded.

The subscription callback endpoint must acknowledge the POST of each new event with a status code of 200 OK within two seconds. Event pushes are retried (up to a total of three attempts) if a 200 is not returned. If your application needs to do more processing of the received information, it should do so asynchronously.

These are the fields that are included with webhook events:

object_type
string	Always either "activity" or "athlete."
object_id
long integer	For activity events, the activity's ID. For athlete events, the athlete's ID.
aspect_type
string	Always "create," "update," or "delete."
updates
hash	For activity update events, keys can contain "title," "type," and "private," which is always "true" (activity visibility set to Only You) or "false" (activity visibility set to Followers Only or Everyone). For app deauthorization events, there is always an "authorized" : "false" key-value pair.
owner_id
long integer	The athlete's ID.
subscription_id
integer	The push subscription ID that is receiving this event.
event_time
long integer	The time that the event occurred.
Example Request
{
    "aspect_type": "update",
    "event_time": 1516126040,
    "object_id": 1360128428,
    "object_type": "activity",
    "owner_id": 134815,
    "subscription_id": 120475,
    "updates": {
        "title": "Messy"
    }
}
Note that a single event can have multiple key-value pairs in updates. Also note that some activity attributes are updated asynchronously, so one “save” action by the athlete can result in multiple webhook events.

For example, if activity type and title are changed, the change to activity type may take place in the background after the title is saved.

Applications that have activity:read scope (recommended) and not activity:read_all scope will receive a delete event when an activity’s visibility is changed from Followers Only or Everyone to Only You. Similarly, these applications will receive a create event when an activity’s visibility is changed from Only You to one of the other settings. Per the Strava API Agreement, applications must respect an activity’s privacy.

Subscriptions
Each application may only have one subscription, but that single subscription will allow the application to receive webhook events for all supported changes to data owned by athletes that have authorized that application. Here is an example of how to create a dummy server to create a webhook subscription.

Webhook subscriptions, also referred to as push subscriptions, are managed through the push subscription API at:

$ https://www.strava.com/api/v3/push_subscriptions
Create a subscription
Creating a new webhook subscription is a two-step process:

Request subscription creation by making a POST request to the subscriptions endpoint. This request includes the application’s client_id and client_secret. It defines the callback address where events will be sent and also defines a verification token used in validating the callback address.
Validate the callback address. The Strava webhook system, upon receiving an subscription creation request, will issue a GET request to the newly defined callback address to validate that it is available. The server serving the callback address must respond to this GET in a timely and correct manner for the subscription to be validated and enabled.
Subscription Creation Request
Note that request parameters must be sent as HTTP form data, i.e. in URL format.

These are the required request parameters to create a webhook events subscription:

client_id
required integer	Strava API application ID
client_secret
required string	Strava API application secret
callback_url
required string	Address where webhook events will be sent; maximum length of 255 characters
verify_token
required string	String chosen by the application owner for client security. An identical string will be included in the validation request made by Strava's subscription service.
Example Request
$  curl -X POST https://www.strava.com/api/v3/push_subscriptions \
      -F client_id=5 \
      -F client_secret=7b2946535949ae70f015d696d8ac602830ece412 \
      -F callback_url=http://a-valid.com/url \
      -F verify_token=STRAVA
Subscription Validation Request
After your initial request to create a subscription, you will receive a HTTP GET request to the callback_url you specified. The query string of this GET request will contain a "hub.challenge" field that you must use to validate your callback address.

Here is the complete list of query string parameters in the validation GET request:

hub.mode
string	Always will be "subscribe".
hub.challenge
string	Random string the callback address must echo back to verify its existence.
hub.verify_token
string	This will be set to whatever verify_token is passed in with the initial subscription request, and it enables application owners to know that they are receiving the correct response from Strava's subscription service.
Example Validation Request
$ GET https://mycallbackurl.com?hub.verify_token=STRAVA&hub.challenge=15f7d1a91c1f40f8a748fd134752feb3&hub.mode=subscribe
Callback Validation
Your callback address must respond within two seconds to the GET request from Strava’s subscription service. The response should indicate status code 200 and should echo the hub.challenge field in the response body as application/json content type: { “hub.challenge”:”15f7d1a91c1f40f8a748fd134752feb3” }

Once you have successfully created a webhook events subscription by responding to the callback validation, you will receive a response to your original subscription creation POST request. This response will include the id of the newly created subscription. If creation of a new subscription fails, this response will instead include error information. The most common cause of subscription creation failure is a failure to respond in a timely manner to the validation GET request, or failure to correctly echo the hub.challenge field.

Example Subscription Creation Response
{
  "id": 1
}
View a Subscription
A GET request to the push subscription endpoint can be used to view subscription details. The request should include the following parameters in the query string:

client_id
required integer	Strava API application ID
client_secret
required string	Strava API application secret
Example Request
$ curl -G https://www.strava.com/api/v3/push_subscriptions \
    -d client_id=5 \
    -d client_secret=7b2946535949ae70f015d696d8ac602830ece412
Delete a Subscription
A DELETE request can be issued to the push subscriptions endpoint, with subscription ID appended, to delete the specified subscription:

$ https://www.strava.com/api/v3/push_subscriptions/id 
The following parameters should be included with a delete request:

id
required integer, in path	Push subscription ID
client_id
required integer, in query parameter	Strava API application ID
client_secret
required string, in query parameter	Strava API application secret
You will receive a 204 No Content if the delete is successful. Otherwise, an error will be returned containing the reason for a failure.

Example Request
$ curl -X DELETE "https://www.strava.com/api/v3/push_subscriptions/12345?client_id=5&client_secret=7b2946535949ae70f015d696d8ac602830ece412"
Troubleshooting Tips
Unable to create a subscription
Check if there is already a subscription registered for your app: View a Subscription. If so, delete it: Delete a Subscription.
Validate that your callback url responds to a validation request within 2 seconds. You can issue a request like the following to test:

$ curl -X GET ‘{your-callback-url}?hub.verify_token=test&hub.challenge=15f7d1a91c1f40f8a748fd134752feb3&hub.mode=subscribe’
Check that the response to the above request shows a 200 status and correctly echos the hub.challenge in the JSON body. The response body to the above sample curl request should look like { “hub.challenge”:”15f7d1a91c1f40f8a748fd134752feb3” }
Not receiving expected events
Check which scopes the athletes using your app have authorized. To receive updates for activities with Only You visibility, your application must have activity:read_all scope for the athlete. To receive updates for activities with Everyone or Followers visibility, your application must have activity:read_all or activity:read scope for the athlete.
Add generic logging and error handling as close to the edge of your network as possible - often an unhandled exception in webhook payload processing is the cause of “missing updates.”
Issue a POST to your callback URL manually to make sure it responds with a 200 status code and does appropriate processing. For example, you can use the following curl command, replacing owner_id, object_id, and subscription_id with your own test athlete id, test activity id, and webhook subscription id, respectively:

$ curl -X POST {your-callback-url} -H ‘Content-Type: application/json’

 -d ‘{
      “aspect_type”: “create”,
      “event_time”: 1549560669,
      “object_id”: 0000000000,
      “object_type”: “activity”,
      “owner_id”: 9999999,
      “subscription_id”: 999999
    }’