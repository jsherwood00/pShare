# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: storage_node.proto
# Protobuf Python Version: 5.29.0
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    29,
    0,
    '',
    'storage_node.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x12storage_node.proto\x12\x07storage\"}\n\x10HeartbeatRequest\x12\x0c\n\x04uuid\x18\x01 \x01(\t\x12\x11\n\ttimestamp\x18\x02 \x01(\x03\x12\x19\n\x11\x66ile_service_port\x18\x03 \x01(\x05\x12\x1b\n\x13storage_capacity_mb\x18\x04 \x01(\x01\x12\x10\n\x08hostname\x18\x05 \x01(\t\"5\n\x11HeartbeatResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t\"J\n\x0bUUIDRequest\x12\x0c\n\x04type\x18\x01 \x01(\t\x12\x1b\n\x13storage_capacity_mb\x18\x02 \x01(\x01\x12\x10\n\x08hostname\x18\x03 \x01(\t\">\n\x0cUUIDResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0c\n\x04uuid\x18\x02 \x01(\t\x12\x0f\n\x07message\x18\x03 \x01(\t\"M\n\x0eUUIDValidation\x12\x0c\n\x04uuid\x18\x01 \x01(\t\x12\x1b\n\x13storage_capacity_mb\x18\x02 \x01(\x01\x12\x10\n\x08hostname\x18\x03 \x01(\t\"R\n\tFileChunk\x12\x0f\n\x07\x63ontent\x18\x01 \x01(\x0c\x12\x10\n\x08\x66ilename\x18\x02 \x01(\t\x12\x0e\n\x06offset\x18\x03 \x01(\x04\x12\x12\n\ntotal_size\x18\x04 \x01(\x04\"\x1f\n\x0b\x46ileRequest\x12\x10\n\x08\x66ilename\x18\x01 \x01(\t\"\x1e\n\nFileDelete\x12\x10\n\x08\x66ilename\x18\x01 \x01(\t\"2\n\x0e\x44\x65leteResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t\">\n\x0c\x46ileResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t\x12\x0c\n\x04size\x18\x03 \x01(\x04\x32\x90\x03\n\x0eStorageService\x12<\n\x0bRequestUUID\x12\x14.storage.UUIDRequest\x1a\x15.storage.UUIDResponse\"\x00\x12@\n\x0cValidateUUID\x12\x17.storage.UUIDValidation\x1a\x15.storage.UUIDResponse\"\x00\x12;\n\nUploadFile\x12\x12.storage.FileChunk\x1a\x15.storage.FileResponse\"\x00(\x01\x12;\n\x0bRequestFile\x12\x14.storage.FileRequest\x1a\x12.storage.FileChunk\"\x00\x30\x01\x12:\n\nDeleteFile\x12\x13.storage.FileDelete\x1a\x15.storage.FileResponse\"\x00\x12H\n\tHeartbeat\x12\x19.storage.HeartbeatRequest\x1a\x1a.storage.HeartbeatResponse\"\x00(\x01\x30\x01\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'storage_node_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_HEARTBEATREQUEST']._serialized_start=31
  _globals['_HEARTBEATREQUEST']._serialized_end=156
  _globals['_HEARTBEATRESPONSE']._serialized_start=158
  _globals['_HEARTBEATRESPONSE']._serialized_end=211
  _globals['_UUIDREQUEST']._serialized_start=213
  _globals['_UUIDREQUEST']._serialized_end=287
  _globals['_UUIDRESPONSE']._serialized_start=289
  _globals['_UUIDRESPONSE']._serialized_end=351
  _globals['_UUIDVALIDATION']._serialized_start=353
  _globals['_UUIDVALIDATION']._serialized_end=430
  _globals['_FILECHUNK']._serialized_start=432
  _globals['_FILECHUNK']._serialized_end=514
  _globals['_FILEREQUEST']._serialized_start=516
  _globals['_FILEREQUEST']._serialized_end=547
  _globals['_FILEDELETE']._serialized_start=549
  _globals['_FILEDELETE']._serialized_end=579
  _globals['_DELETERESPONSE']._serialized_start=581
  _globals['_DELETERESPONSE']._serialized_end=631
  _globals['_FILERESPONSE']._serialized_start=633
  _globals['_FILERESPONSE']._serialized_end=695
  _globals['_STORAGESERVICE']._serialized_start=698
  _globals['_STORAGESERVICE']._serialized_end=1098
# @@protoc_insertion_point(module_scope)
