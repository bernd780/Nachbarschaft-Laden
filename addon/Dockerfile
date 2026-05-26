ARG BUILD_FROM
FROM $BUILD_FROM

ARG CACHEBUST=13
RUN echo "cachebust=$CACHEBUST"

RUN apk add --no-cache \
    gcc musl-dev libffi-dev \
    jpeg-dev zlib-dev freetype-dev \
    ttf-dejavu \
    nginx jq tzdata curl

RUN pip install --no-cache-dir \
    appdaemon==4.4.2 \
    pillow \
    qrcode[pil]

COPY run.sh /run.sh
RUN sed -i 's/\r//' /run.sh && chmod +x /run.sh

COPY apps/ /apps/
COPY www/  /www/

CMD ["/run.sh"]
