# coding: utf-8

"""
    fatcat

    Fatcat is a scalable, versioned, API-oriented catalog of bibliographic entities and file metadata.   # noqa: E501

    The version of the OpenAPI document: 0.3.1
    Contact: webservices@archive.org
    Generated by: https://openapi-generator.tech
"""


import pprint
import re  # noqa: F401

import six


class ErrorResponse(object):
    """NOTE: This class is auto generated by OpenAPI Generator.
    Ref: https://openapi-generator.tech

    Do not edit the class manually.
    """

    """
    Attributes:
      openapi_types (dict): The key is attribute name
                            and the value is attribute type.
      attribute_map (dict): The key is attribute name
                            and the value is json key in definition.
    """
    openapi_types = {
        'success': 'bool',
        'error': 'str',
        'message': 'str'
    }

    attribute_map = {
        'success': 'success',
        'error': 'error',
        'message': 'message'
    }

    def __init__(self, success=None, error=None, message=None):  # noqa: E501
        """ErrorResponse - a model defined in OpenAPI"""  # noqa: E501

        self._success = None
        self._error = None
        self._message = None
        self.discriminator = None

        self.success = success
        self.error = error
        self.message = message

    @property
    def success(self):
        """Gets the success of this ErrorResponse.  # noqa: E501


        :return: The success of this ErrorResponse.  # noqa: E501
        :rtype: bool
        """
        return self._success

    @success.setter
    def success(self, success):
        """Sets the success of this ErrorResponse.


        :param success: The success of this ErrorResponse.  # noqa: E501
        :type: bool
        """
        if success is None:
            raise ValueError("Invalid value for `success`, must not be `None`")  # noqa: E501

        self._success = success

    @property
    def error(self):
        """Gets the error of this ErrorResponse.  # noqa: E501


        :return: The error of this ErrorResponse.  # noqa: E501
        :rtype: str
        """
        return self._error

    @error.setter
    def error(self, error):
        """Sets the error of this ErrorResponse.


        :param error: The error of this ErrorResponse.  # noqa: E501
        :type: str
        """
        if error is None:
            raise ValueError("Invalid value for `error`, must not be `None`")  # noqa: E501

        self._error = error

    @property
    def message(self):
        """Gets the message of this ErrorResponse.  # noqa: E501


        :return: The message of this ErrorResponse.  # noqa: E501
        :rtype: str
        """
        return self._message

    @message.setter
    def message(self, message):
        """Sets the message of this ErrorResponse.


        :param message: The message of this ErrorResponse.  # noqa: E501
        :type: str
        """
        if message is None:
            raise ValueError("Invalid value for `message`, must not be `None`")  # noqa: E501

        self._message = message

    def to_dict(self):
        """Returns the model properties as a dict"""
        result = {}

        for attr, _ in six.iteritems(self.openapi_types):
            value = getattr(self, attr)
            if isinstance(value, list):
                result[attr] = list(map(
                    lambda x: x.to_dict() if hasattr(x, "to_dict") else x,
                    value
                ))
            elif hasattr(value, "to_dict"):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = dict(map(
                    lambda item: (item[0], item[1].to_dict())
                    if hasattr(item[1], "to_dict") else item,
                    value.items()
                ))
            else:
                result[attr] = value

        return result

    def to_str(self):
        """Returns the string representation of the model"""
        return pprint.pformat(self.to_dict())

    def __repr__(self):
        """For `print` and `pprint`"""
        return self.to_str()

    def __eq__(self, other):
        """Returns true if both objects are equal"""
        if not isinstance(other, ErrorResponse):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
