# Acquisition Policy

Acquisition records are source-contact records, not strategy evidence by themselves.

A record may later contribute to semantic evidence only when its payload came from direct first-party contact and is SHA-256 bound. `ENVIRONMENT_ACCESS_FAILURE`, `SOURCE_CONTACTED_NO_PAYLOAD`, locator-only records, fixture-only records, and secondary locator sources must not be converted into strategy absence/presence claims.

The repository must keep raw bulk source payloads outside Git by default and preserve only durable manifests, hashes, and later minimal legally appropriate evidence excerpts.
