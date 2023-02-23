# Customization Details


## Sanitizer Registrations



## Matcher Registrations


## Transform Registrations

Usage of transforms outside of the default are faily uncommon. These customizations are applied when a previously recorded **response** needs to be `transform`-ed according to some value in the **request**.

The test-proxy has **two** transforms active by default. Namely: `StorageRequestIdTransform`, `ClientIdTransform`, and a `HeaderTransform` that rewrites `Retry-After` to 0 if it is present.

- `StorageRequestIdTransform` replaces the matched **response** header `x-ms-client-request-id` with the value from the same header in incoming **request**.
- `ClientIdTransform` replaces the matched **response** header `x-ms-client-id` with the value from the same header in incoming **request**.

### Example POST requests

TODO: fill these in


## Restrictions of sending regex in a JSON

Unfortunately, due to the fact that the test-proxy accepts all of these customizations as members of a JSON Body, there is a restriction to be aware of when dealing with passing of `regex` values.

Let's show an example of needing to use the `\` escape character.

```jsonc
// HEADERS
{
   "x-abstraction-identifier": "GeneralRegexSanitizer"
}

// BODY
{ 
   "target": "HEADER", 
   "regex": "/login\\\\.microsoftonline.com"
}
```

Notice the perculiar `\\\\` within the body. This is present due to restrictions on json string values. According [to the json spec](https://www.json.org/img/string.png), a string can only contain a `\` when it is followed by:

- `"` -> `\"`
- `\` -> `\\`
- `/` -> `\/`
- `b` -> `\b`
- `f` -> `\f`
- `n` -> `\n`
- `r` -> `\r`
- `t` -> `\t`
- `u<4 hex digits>` -> `\u0002`

This means to properly send a regex, a string must be **double escaped** so that the parsing of the json is not broken. It is best do this in the test framework that is sending the POST request that registers a sanitizer. Simply replace all incidences of backslash with two backslashes.

- Actual Regex: `login\.microsoftonline.com`, which will match the `.` literally.
- What should be sent in your json body: `login\\.microsoftonline.com`.

Of course, the above is what the _rendered_ string looks like. Here is an actual json body:

```jsonc
{ 
   "target": "HEADER", 
   "regex": "/login\\\\.microsoftonline.com"
}
```

Notice that a single escaped `\` becomes two.
