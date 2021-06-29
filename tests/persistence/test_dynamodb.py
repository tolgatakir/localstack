import logging
import os

from localstack.utils.common import short_uid

LOG = logging.getLogger(__name__)


def test_dynamodb_persistence(persistent_runtime, dynamodb):
    table_name = 'table-' + short_uid()

    # pre-assert
    assert table_name not in dynamodb.list_tables()['TableNames']

    dynamodb.create_table(
        TableName=table_name,
        KeySchema=[{
            'AttributeName': 'id', 'KeyType': 'HASH'
        }],
        AttributeDefinitions=[{
            'AttributeName': 'id', 'AttributeType': 'S'
        }],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5
        },
        Tags=[{'Key': 'Name', 'Value': 'test-table'}, {'Key': 'TestKey', 'Value': 'true'}]
    )

    assert table_name in dynamodb.list_tables()['TableNames']

    assert persistent_runtime.runtime.reset(timeout=30)
    assert persistent_runtime.runtime.start(timeout=30)
    assert table_name in dynamodb.list_tables()['TableNames']
