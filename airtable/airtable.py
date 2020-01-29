"""

Airtable Class Instance
***********************

>>> airtable = Airtable('base_key', 'table_name')
>>> airtable.get_all()
[{id:'rec123asa23', fields': {'Column': 'Value'}, ...}]

For more information on Api Key and authentication see
the :doc:`authentication`.

------------------------------------------------------------------------

Examples
********

For a full list of available methods see the :any:`Airtable` class below.
For more details on the Parameter filters see the documentation on the
available :doc:`params` as well as the
`Airtable API Docs <http://airtable.com/api>`_

Record/Page Iterator:

>>> for page in airtable.get_iter(view='ViewName',sort='COLUMN_A'):
...     for record in page:
...         value = record['fields']['COLUMN_A']

Get all Records:

>>> airtable.get_all(view='ViewName',sort='COLUMN_A')
[{id:'rec123asa23', 'fields': {'COLUMN_A': 'Value', ...}, ... ]

Search:

>>> airtable.search('ColumnA', 'SearchValue')

Formulas:

>>> airtable.get_all(formula="FIND('DUP', {COLUMN_STR})=1")


Insert:

>>> airtable.insert({'First Name', 'John'})

Delete:

>>> airtable.delete('recwPQIfs4wKPyc9D')


You can see the Airtable Class in action in this
`Jupyter Notebook <https://github.com/gtalarico/airtable-python-wrapper/blob/master/Airtable.ipynb>`_

------------------------------------------------------------------------

Return Values
**************

Return Values: when records are returned,
they will most often be a list of Airtable records (dictionary) in a format
similar to this:

>>> [{
...     "records": [
...         {
...             "id": "recwPQIfs4wKPyc9D",
...             "fields": {
...                 "COLUMN_ID": "1",
...             },
...             "createdTime": "2017-03-14T22:04:31.000Z"
...         },
...         {
...             "id": "rechOLltN9SpPHq5o",
...             "fields": {
...                 "COLUMN_ID": "2",
...             },
...             "createdTime": "2017-03-20T15:21:50.000Z"
...         },
...         {
...             "id": "rec5eR7IzKSAOBHCz",
...             "fields": {
...                 "COLUMN_ID": "3",
...             },
...             "createdTime": "2017-08-05T21:47:52.000Z"
...         }
...     ],
...     "offset": "rec5eR7IzKSAOBHCz"
... }, ... ]

"""  #

import sys
import requests
from collections import OrderedDict
import posixpath
import time
import json
from six.moves.urllib.parse import unquote, quote, urlencode
from six.moves import range
from six import string_types

from .auth import AirtableAuth
from .params import AirtableParams

try:
    IS_IPY = sys.implementation.name == "ironpython"
except AttributeError:
    IS_IPY = False


class Airtable:

    VERSION = "v0"
    API_BASE_URL = "https://api.airtable.com/"
    API_LIMIT = 1.0 / 5  # 5 per second
    API_URL = posixpath.join(API_BASE_URL, VERSION)
    MAX_RECORDS_PER_CALL = 10

    def __init__(self, base_key, table_name, api_key=None):
        """
        If api_key is not provided, :any:`AirtableAuth` will attempt
        to use ``os.environ['AIRTABLE_API_KEY']``
        """
        session = requests.Session()
        session.auth = AirtableAuth(api_key=api_key)
        self.session = session
        self.table_name = table_name
        url_safe_table_name = quote(table_name, safe="")
        self.url_table = posixpath.join(self.API_URL, base_key, url_safe_table_name)

    def _process_params(self, params):
        """
        Process params names or values as needed using filters
        """
        new_params = OrderedDict()
        for param_name, param_value in sorted(params.items()):
            param_value = params[param_name]
            ParamClass = AirtableParams._get(param_name)
            new_params.update(ParamClass(param_value).to_param_dict())
        return new_params

    def _process_response(self, response):
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            err_msg = str(exc)

            # Reports Decoded 422 Url for better troubleshooting
            # Disabled in IronPython Bug:
            # https://github.com/IronLanguages/ironpython2/issues/242
            if not IS_IPY and response.status_code == 422:
                err_msg = err_msg.replace(response.url, unquote(response.url))
                err_msg += " (Decoded URL)"

            # Attempt to get Error message from response, Issue #16
            try:
                error_dict = response.json()
            except json.decoder.JSONDecodeError:
                pass
            else:
                if "error" in error_dict:
                    err_msg += " [Error: {}]".format(error_dict["error"])
            raise requests.exceptions.HTTPError(err_msg)
        else:
            return response.json()

    def record_url(self, record_id):
        """ Builds URL with record id """
        return posixpath.join(self.url_table, record_id)

    def _request(self, method, url, params=None, json_data=None):
        response = self.session.request(method, url, params=params, json=json_data)
        return self._process_response(response)

    def _get(self, url, **params):
        processed_params = self._process_params(params)
        return self._request("get", url, params=processed_params)

    def _post(self, url, json_data):
        return self._request("post", url, json_data=json_data)

    def _put(self, url, json_data):
        return self._request("put", url, json_data=json_data)

    def _patch(self, url, json_data):
        return self._request("patch", url, json_data=json_data)

    def _delete(self, url):
        return self._request("delete", url)

    def get(self, record_id):
        """
        Retrieves a record by its id

        >>> record = airtable.get('recwPQIfs4wKPyc9D')

        Args:
            record_id(``str``): Airtable record id

        Returns:
            record (``dict``): Record
        """
        record_url = self.record_url(record_id)
        return self._get(record_url)

    def get_iter(self, **options):
        """
        Record Retriever Iterator

        Returns iterator with lists in batches according to pageSize.
        To get all records at once use :any:`get_all`

        >>> for page in airtable.get_iter():
        ...     for record in page:
        ...         print(record)
        [{'fields': ... }, ...]

        Keyword Args:
            max_records (``int``, optional): The maximum total number of
                records that will be returned. See :any:`MaxRecordsParam`
            view (``str``, optional): The name or ID of a view.
                See :any:`ViewParam`.
            page_size (``int``, optional ): The number of records returned
                in each request. Must be less than or equal to 100.
                Default is 100. See :any:`PageSizeParam`.
            fields (``str``, ``list``, optional): Name of field or fields to
                be retrieved. Default is all fields. See :any:`FieldsParam`.
            sort (``list``, optional): List of fields to sort by.
                Default order is ascending. See :any:`SortParam`.
            formula (``str``, optional): Airtable formula.
                See :any:`FormulaParam`.

        Returns:
            iterator (``list``): List of Records, grouped by pageSize

        """
        offset = None
        while True:
            data = self._get(self.url_table, offset=offset, **options)
            records = data.get("records", [])
            time.sleep(self.API_LIMIT)
            yield records
            offset = data.get("offset")
            if not offset:
                break

    def get_all(self, **options):
        """
        Retrieves all records repetitively and returns a single list.

        >>> airtable.get_all()
        >>> airtable.get_all(view='MyView', fields=['ColA', '-ColB'])
        >>> airtable.get_all(maxRecords=50)
        [{'fields': ... }, ...]

        Keyword Args:
            max_records (``int``, optional): The maximum total number of
                records that will be returned. See :any:`MaxRecordsParam`
            view (``str``, optional): The name or ID of a view.
                See :any:`ViewParam`.
            fields (``str``, ``list``, optional): Name of field or fields to
                be retrieved. Default is all fields. See :any:`FieldsParam`.
            sort (``list``, optional): List of fields to sort by.
                Default order is ascending. See :any:`SortParam`.
            formula (``str``, optional): Airtable formula.
                See :any:`FormulaParam`.

        Returns:
            records (``list``): List of Records

        >>> records = get_all(maxRecords=3, view='All')

        """
        all_records = []
        for records in self.get_iter(**options):
            all_records.extend(records)
        return all_records

    def match(self, field_name, field_value, **options):
        """
        Returns first match found in :any:`get_all`

        >>> airtable.match('Name', 'John')
        {'fields': {'Name': 'John'} }

        Args:
            field_name (``str``): Name of field to match (column name).
            field_value (``str``): Value of field to match.

        Keyword Args:
            max_records (``int``, optional): The maximum total number of
                records that will be returned. See :any:`MaxRecordsParam`
            view (``str``, optional): The name or ID of a view.
                See :any:`ViewParam`.
            fields (``str``, ``list``, optional): Name of field or fields to
                be retrieved. Default is all fields. See :any:`FieldsParam`.
            sort (``list``, optional): List of fields to sort by.
                Default order is ascending. See :any:`SortParam`.

        Returns:
            record (``dict``): First record to match the field_value provided
        """
        from_name_and_value = AirtableParams.FormulaParam.from_name_and_value
        formula = from_name_and_value(field_name, field_value)
        options["formula"] = formula
        for record in self.get_all(**options):
            return record
        else:
            return {}

    def search(self, field_name, field_value, record=None, **options):
        """
        Returns all matching records found in :any:`get_all`

        >>> airtable.search('Gender', 'Male')
        [{'fields': {'Name': 'John', 'Gender': 'Male'}, ... ]

        Args:
            field_name (``str``): Name of field to match (column name).
            field_value (``str``): Value of field to match.

        Keyword Args:
            max_records (``int``, optional): The maximum total number of
                records that will be returned. See :any:`MaxRecordsParam`
            view (``str``, optional): The name or ID of a view.
                See :any:`ViewParam`.
            fields (``str``, ``list``, optional): Name of field or fields to
                be retrieved. Default is all fields. See :any:`FieldsParam`.
            sort (``list``, optional): List of fields to sort by.
                Default order is ascending. See :any:`SortParam`.

        Returns:
            records (``list``): All records that matched ``field_value``

        """
        records = []
        from_name_and_value = AirtableParams.FormulaParam.from_name_and_value
        formula = from_name_and_value(field_name, field_value)
        options["formula"] = formula
        records = self.get_all(**options)
        return records

    def insert(self, fields_or_records, typecast=False):
        """
        Inserts up to airtable.MAX_RECORDS_PER_CALL records

        Insert a single record:

        >>> record = {'Name': 'John'}
        >>> airtable.insert(record)

        Insert multiple records:

        >>> records = [{'Name': 'John'}, {'Name': 'Steve'}]
        >>> airtable.insert(records)

        Args:
            fields_or_records(``dict`` or ``Iterable``): Fields or records to insert.
                Must be either dictionary with Column names as Key or Iterable of such dictionaries.
            typecast(``boolean``): Automatic data conversion from string values.

        Returns:
            records (``dict`` or ``list``): Inserted record or list of inserted records.

        """

        # if fields_or_records is a dict, assume it's the fields for a single record
        if isinstance(fields_or_records, dict):
            fields = fields_or_records

            return self._post(
                self.url_table, json_data={"fields": fields, "typecast": typecast}
            )

        # otherwise, assume an iterable of records was passed in.
        records = [{'fields': fields} for fields in fields_or_records]

        if len(records) > self.MAX_RECORDS_PER_CALL:
            raise RuntimeError(
                'Only {} records can be inserted per call'.format(self.MAX_RECORDS_PER_CALL)
            )

        return self._post(
            self.url_table, json_data={"records": records, "typecast": typecast}
        )

    def chunker(self, seq):
        """
        Iterates over chunks of an iterable.
        Each chunk has length less than or equal to self.MAX_RECORDS_PER_CALL
        Based on nosklo's answer to this Stack Overflow question:
        https://stackoverflow.com/questions/434287/what-is-the-most-pythonic-way-to-iterate-over-a-list-in-chunks
        """
        return (seq[pos:pos + self.MAX_RECORDS_PER_CALL] for pos in range(0, len(seq), self.MAX_RECORDS_PER_CALL))

    def _batch_request(self, func, iterable, **kwargs):
        """ Internal Function to limit batch calls to API limit """
        responses = []
        for iterable_chunk in self.chunker(iterable):
            responses.extend(func(iterable_chunk, **kwargs))
            time.sleep(self.API_LIMIT)
        return responses

    def batch_insert(self, records, typecast=False):
        """
        Calls :any:`insert` repetitively, following set API Rate Limit (5/sec)
        To change the rate limit use ``airtable.API_LIMIT = 0.2``
        (5 per second)

        >>> records = [{'Name': 'John'}, {'Name': 'Marc'}]
        >>> airtable.batch_insert(records)

        Args:
            records(``list``): Records to insert
            typecast(``boolean``): Automatic data conversion from string values.

        Returns:
            records (``list``): list of added records

        """
        return self._batch_request(self.insert, records, typecast=typecast)

    def update_records(self, records, typecast=False):
        """
        Updates up to airtable.MAX_RECORDS_PER_CALL records
        Also used for batch_update

        >>> records = [airtable.match('Employee Id', 'DD13332454'), airtable.match('Employee Id', 'DD12312378')]
        >>> updates = [{'id': records[0]['id'], 'Status': 'Fired'}, {'id': records[1]['id'], 'Status': 'Hired'}]
        >>> airtable.update_records(updates)

        Args:
            records(``Iterable``): Iterable of dictionaries with 'fields' equal to a dictionary of Column names as Key and 'id' equal to Id of Record.
            typecast(``boolean``): Automatic data conversion from string values.

        Returns:
            records (``list``): List of inserted records.

        """

        records = list(records)

        if len(records) > self.MAX_RECORDS_PER_CALL:
            raise RuntimeError(
                'Only {} records can be updated per call'.format(self.MAX_RECORDS_PER_CALL)
            )

        return self._patch(
            self.url_table, json_data={"records": records, "typecast": typecast}
        )

    def update(self, record_id=None, fields=None, typecast=False, records=None):
        """
        Updates up to airtable.MAX_RECORDS_PER_CALL records by record_id
        Only Fields passed are updated, the rest are left as is.

        Update a single record:

        >>> record = airtable.match('Employee Id', 'DD13332454')
        >>> fields = {'Status': 'Fired'}
        >>> airtable.update(record['id'], fields)

        Update multiple records:

        >>> records = [airtable.match('Employee Id', 'DD13332454'), airtable.match('Employee Id', 'DD12312378')]
        >>> updates = [{'id': records[0]['id'], 'Status': 'Fired'}, {'id': records[1]['id'], 'Status': 'Hired'}]
        >>> airtable.update(records=updates)

        Args:
            record_id(``str``): Id of Record to update (if updating single record)
            fields(``dict``): Fields to update (if updating single record)
                Must be dictionary with Column names as Key
            typecast(``boolean``): Automatic data conversion from string values.
            records(``Iterable``): Iterable of dictionaries with 'fields' equal to a dictionary of Column names as Key and 'id' equal to Id of Record.
                Only required if updating multiple records.

        Returns:
            record (``dict`` or ``list``): Updated record or list of updated records
        """

        # if record_id and fields are set, assume we are updating a single record
        if record_id and fields:
            record_url = self.record_url(record_id)
            return self._patch(
                record_url, json_data={"fields": fields, "typecast": typecast}
            )

        # otherwise, check for records:
        if records:
            return self.update_records(records)

        # inputs were not set correctly
        raise RuntimeError(
            'update must have record_id and fields set OR records set'
        )

    def update_by_field(
        self, field_name, field_value, fields, typecast=False, **options
    ):
        """
        Updates the first record to match field name and value.
        Only Fields passed are updated, the rest are left as is.

        >>> record = {'Name': 'John', 'Tel': '540-255-5522'}
        >>> airtable.update_by_field('Name', 'John', record)

        Args:
            field_name (``str``): Name of field to match (column name).
            field_value (``str``): Value of field to match.
            fields(``dict``): Fields to update.
                Must be dictionary with Column names as Key
            typecast(``boolean``): Automatic data conversion from string values.

        Keyword Args:
            view (``str``, optional): The name or ID of a view.
                See :any:`ViewParam`.
            sort (``list``, optional): List of fields to sort by.
                Default order is ascending. See :any:`SortParam`.

        Returns:
            record (``dict``): Updated record
        """
        record = self.match(field_name, field_value, **options)
        return {} if not record else self.update(record["id"], fields, typecast)

    def batch_update(self, records, typecast=False):
        """
        Calls :any:`update_records` repetitively, following set API Rate Limit (5/sec)
        To change the rate limit use ``airtable.API_LIMIT = 0.2``
        (5 per second)

        >>> records = [{'id': 'recXXXXXXXXXXXXXX', 'Name': 'John'}, {'id': 'recYYYYYYYYYYYYYY', 'Name': 'Marc'}]
        >>> airtable.batch_update(records)

        Args:
            records(``Iterable``): Records to update
            typecast(``boolean``): Automatic data conversion from string values.

        Returns:
            records (``list``): list of updated records

        """
        return self._batch_request(self.update_records, records, typecast=typecast)

    def replace(self, record_id, fields, typecast=False):
        """
        Replaces a record by its record id.
        All Fields are updated to match the new ``fields`` provided.
        If a field is not included in ``fields``, value will bet set to null.
        To update only selected fields, use :any:`update`.

        >>> record = airtable.match('Seat Number', '22A')
        >>> fields = {'PassangerName': 'Mike', 'Passport': 'YASD232-23'}
        >>> airtable.replace(record['id'], fields)

        Args:
            record_id(``str``): Id of Record to update
            fields(``dict``): Fields to replace with.
                Must be dictionary with Column names as Key.
            typecast(``boolean``): Automatic data conversion from string values.

        Returns:
            record (``dict``): New record
        """
        record_url = self.record_url(record_id)
        return self._put(record_url, json_data={"fields": fields, "typecast": typecast})

    def replace_by_field(
        self, field_name, field_value, fields, typecast=False, **options
    ):
        """
        Replaces the first record to match field name and value.
        All Fields are updated to match the new ``fields`` provided.
        If a field is not included in ``fields``, value will bet set to null.
        To update only selected fields, use :any:`update`.

        Args:
            field_name (``str``): Name of field to match (column name).
            field_value (``str``): Value of field to match.
            fields(``dict``): Fields to replace with.
                Must be dictionary with Column names as Key.
            typecast(``boolean``): Automatic data conversion from string values.

        Keyword Args:
            view (``str``, optional): The name or ID of a view.
                See :any:`ViewParam`.
            sort (``list``, optional): List of fields to sort by.
                Default order is ascending. See :any:`SortParam`.

        Returns:
            record (``dict``): New record
        """
        record = self.match(field_name, field_value, **options)
        return {} if not record else self.replace(record["id"], fields, typecast)

    def delete(self, record_id_or_record_ids):
        """
        Deletes up to airtable.MAX_RECORDS_PER_CALL records by record_id

        For a single record:
        >>> record = airtable.match('Employee Id', 'DD13332454')
        >>> airtable.delete(record['id'])

        For multiple records:
        >>> records = [airtable.match('Employee Id', 'DD13332454'), airtable.match('Employee Id', 'QQ4545433')]
        >>> airtable.delete([record['id'] for record in records])

        Args:
            record_id(``str`` or ``Iterable``): Airtable record id or Iterable of record_ids

        Returns:
            record (``dict`` or ``list``): Deleted Record or list of deleted records
        """

        # if a string was passed, assume it's a record_id
        if isinstance(record_id_or_record_ids, string_types):
            record_id = record_id_or_record_ids
            record_url = self.record_url(record_id)
            return self._delete(record_url)

        # otherwise, assume an iterable of record_ids
        record_ids = list(record_id_or_record_ids)

        if len(record_ids) > self.MAX_RECORDS_PER_CALL:
            raise RuntimeError(
                'Only {} records can be deleted per call'.format(self.MAX_RECORDS_PER_CALL)
            )

        params = {'records[]': record_ids}
        url_encoded_record_ids = urlencode(params, True)
        delete_url = '{}?{}'.format(self.url_table, url_encoded_record_ids)
        return self._delete(delete_url)

    def delete_by_field(self, field_name, field_value, **options):
        """
        Deletes first record  to match provided ``field_name`` and
        ``field_value``.

        >>> record = airtable.delete_by_field('Employee Id', 'DD13332454')

        Args:
            field_name (``str``): Name of field to match (column name).
            field_value (``str``): Value of field to match.

        Keyword Args:
            view (``str``, optional): The name or ID of a view.
                See :any:`ViewParam`.
            sort (``list``, optional): List of fields to sort by.
                Default order is ascending. See :any:`SortParam`.

        Returns:
            record (``dict``): Deleted Record
        """
        record = self.match(field_name, field_value, **options)
        record_url = self.record_url(record["id"])
        return self._delete(record_url)

    def batch_delete(self, record_ids):
        """
        Calls :any:`delete` repetitively, following set API Rate Limit (5/sec)
        To change the rate limit set value of ``airtable.API_LIMIT`` to
        the time in seconds it should sleep before calling the function again.

        >>> record_ids = ['recwPQIfs4wKPyc9D', 'recwDxIfs3wDPyc3F']
        >>> airtable.batch_delete(records_ids)

        Args:
            records(``list``): Record Ids to delete

        Returns:
            records(``list``): list of records deleted

        """
        return self._batch_request(self.delete, record_ids)

    def mirror(self, records, **options):
        """
        Deletes all records on table or view and replaces with records.

        >>> records = [{'Name': 'John'}, {'Name': 'Marc'}]

        >>> record = airtable.,mirror(records)

        If view options are provided, only records visible on that view will
        be deleted.

        >>> record = airtable.mirror(records, view='View')
        ([{'id': 'recwPQIfs4wKPyc9D', ... }], [{'deleted': True, ... }])

        Args:
            records(``list``): Records to insert

        Keyword Args:
            max_records (``int``, optional): The maximum total number of
                records that will be returned. See :any:`MaxRecordsParam`
            view (``str``, optional): The name or ID of a view.
                See :any:`ViewParam`.

        Returns:
            records (``tuple``): (new_records, deleted_records)
        """

        all_record_ids = [r["id"] for r in self.get_all(**options)]
        deleted_records = self.batch_delete(all_record_ids)
        new_records = self.batch_insert(records)
        return (new_records, deleted_records)

    def __repr__(self):
        return "<Airtable table:{}>".format(self.table_name)
