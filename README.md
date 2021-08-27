# Apolpi

[![Docker Repository on Quay](https://quay.io/repository/galaxy-genome-annotation/apolpi/status "Docker Repository on Quay")](https://quay.io/repository/galaxy-genome-annotation/apolpi) ![Lint](https://github.com/galaxy-genome-annotation/apolpi/workflows/Lint/badge.svg)

This is a tiny Flask application reimplementing a specific API function (organism listing) of [Apollo](https://github.com/GMOD/apollo), to make it run way faster.

See https://github.com/GMOD/Apollo/issues/2626 for more details on why we implemented it.

## Running with docker-compose

A typical docker-compose.yml to run this app looks like that:

```
version: '3.7'
  services:

    apolpi:
    	image: quay.io/galaxy-genome-annotation/apolpi
            environment:
                SQLALCHEMY_DATABASE_URI: "postgresql://username:password@localhost:5432/apollo"
```

## Configuring Nginx proxy

You need to configure your reverse proxy (Nginx for example) to redirect the traffic for this specific API endpoint, like this:

```
location /apollo/organism/findAllOrganisms {
   proxy_pass http://127.0.0.1:80/organism/findAllOrganisms;
}
```

The rest of the API traffic need to be proxied to the normal Apollo application as usual.

## Required env variables

* SQLALCHEMY_DATABASE_URI *Connection Uri to the postgres database of Apollo*
