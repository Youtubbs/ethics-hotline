from unittest.mock import MagicMock
from botocore.exceptions import ClientError, BotoCoreError

from ethics_hotline.aws.comprehend import ComprehendClient
from ethics_hotline.aws.textract import TextractClient
from ethics_hotline.aws.s3 import S3Client
from ethics_hotline.errors import UpstreamAIError


def client_error(op: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "rate limited"}}, op
    )


def check_comprehend() -> None:
    session = MagicMock()
    client = MagicMock()
    session.client.return_value = client

    client.detect_pii_entities.side_effect = client_error("DetectPiiEntities")
    wrapper = ComprehendClient(session)
    try:
        wrapper.detect_pii_entities("hello")
        raise AssertionError("expected UpstreamAIError")
    except UpstreamAIError as exc:
        print("comprehend failure ->", exc.code, exc.http_status)

    client.detect_pii_entities.side_effect = None
    client.detect_pii_entities.return_value = {"Entities": [{"Type": "EMAIL"}]}
    print("comprehend pii happy ->", wrapper.detect_pii_entities("hello"))

    client.detect_key_phrases.return_value = {"KeyPhrases": [{"Text": "urgent matter"}]}
    print("comprehend key phrases happy ->", wrapper.detect_key_phrases("hello"))


def check_textract() -> None:
    session = MagicMock()
    client = MagicMock()
    session.client.return_value = client
    wrapper = TextractClient(session)

    client.detect_document_text.side_effect = BotoCoreError()
    try:
        wrapper.detect_document_text(b"bytes")
        raise AssertionError("expected UpstreamAIError")
    except UpstreamAIError as exc:
        print("textract failure ->", exc.code, exc.http_status)

    client.detect_document_text.side_effect = None
    client.detect_document_text.return_value = {"Blocks": []}
    print("textract empty page (not an error) ->", wrapper.detect_document_text(b"bytes"))

    client.detect_document_text.return_value = {
        "Blocks": [
            {"BlockType": "LINE", "Text": "first line"},
            {"BlockType": "WORD", "Text": "first"},
            {"BlockType": "LINE", "Text": "second line"},
        ]
    }
    print("textract lines happy ->", wrapper.detect_document_text(b"bytes"))


def check_s3() -> None:
    session = MagicMock()
    client = MagicMock()
    session.client.return_value = client
    wrapper = S3Client(session, bucket="test-bucket")

    key = wrapper.put_object(b"data", "png")
    print("s3 put key (non-guessable) ->", key)
    print("bucket used ->", client.put_object.call_args.kwargs.get("Bucket"))

    client.get_object.side_effect = client_error("GetObject")
    try:
        wrapper.get_object(key)
        raise AssertionError("expected UpstreamAIError")
    except UpstreamAIError as exc:
        print("s3 get failure ->", exc.code, exc.http_status)


if __name__ == "__main__":
    check_comprehend()
    check_textract()
    check_s3()
    print("all AWS wrapper checks passed")
