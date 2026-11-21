FROM alpine:3.20

RUN apk add --no-cache minio curl

EXPOSE 9000 9001

ENTRYPOINT ["minio"]
CMD ["server", "--console-address", ":9001", "/data"]
