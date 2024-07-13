FROM python:3.9-alpine

ARG ARCH=arm64

RUN apk add --update git bash curl unzip zip openssl make python3-dev gcc musl-dev linux-headers openssl-dev zlib-dev libffi-dev cairo-dev pango-dev gdk-pixbuf-dev

ENV TERRAFORM_VERSION="1.4.6"

ENV ARCH $ARCH


RUN curl https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${ARCH}.zip > terraform_${TERRAFORM_VERSION}_linux_${ARCH}.zip && \
  unzip terraform_${TERRAFORM_VERSION}_linux_${ARCH}.zip -d /usr/local/bin && \
  rm -f terraform_${TERRAFORM_VERSION}_linux_${ARCH}.zip

RUN pip install awscli boto3


CMD terraform
