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


class WebcaptureAutoBatch(object):
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
        'editgroup': 'Editgroup',
        'entity_list': 'list[WebcaptureEntity]'
    }

    attribute_map = {
        'editgroup': 'editgroup',
        'entity_list': 'entity_list'
    }

    def __init__(self, editgroup=None, entity_list=None):  # noqa: E501
        """WebcaptureAutoBatch - a model defined in OpenAPI"""  # noqa: E501

        self._editgroup = None
        self._entity_list = None
        self.discriminator = None

        self.editgroup = editgroup
        self.entity_list = entity_list

    @property
    def editgroup(self):
        """Gets the editgroup of this WebcaptureAutoBatch.  # noqa: E501


        :return: The editgroup of this WebcaptureAutoBatch.  # noqa: E501
        :rtype: Editgroup
        """
        return self._editgroup

    @editgroup.setter
    def editgroup(self, editgroup):
        """Sets the editgroup of this WebcaptureAutoBatch.


        :param editgroup: The editgroup of this WebcaptureAutoBatch.  # noqa: E501
        :type: Editgroup
        """
        if editgroup is None:
            raise ValueError("Invalid value for `editgroup`, must not be `None`")  # noqa: E501

        self._editgroup = editgroup

    @property
    def entity_list(self):
        """Gets the entity_list of this WebcaptureAutoBatch.  # noqa: E501


        :return: The entity_list of this WebcaptureAutoBatch.  # noqa: E501
        :rtype: list[WebcaptureEntity]
        """
        return self._entity_list

    @entity_list.setter
    def entity_list(self, entity_list):
        """Sets the entity_list of this WebcaptureAutoBatch.


        :param entity_list: The entity_list of this WebcaptureAutoBatch.  # noqa: E501
        :type: list[WebcaptureEntity]
        """
        if entity_list is None:
            raise ValueError("Invalid value for `entity_list`, must not be `None`")  # noqa: E501

        self._entity_list = entity_list

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
        if not isinstance(other, WebcaptureAutoBatch):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
