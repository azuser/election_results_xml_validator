"""Unit tests for rules.py that leverage the mock_open dependency."""

import inspect

from absl.testing import absltest
from election_results_xml_validator import rules
from lxml import etree
from mock import MagicMock
from mock import mock_open
from mock import patch


class ElectoralDistrictOcdIdTest(absltest.TestCase):

  def setUp(self):
    super(ElectoralDistrictOcdIdTest, self).setUp()
    root_string = """
      <ElectionReport>
        <GpUnitCollection>
          <GpUnit/>
          <GpUnit/>
          <GpUnit/>
        </GpUnitCollection>
      </ElectionReport>
    """
    election_tree = etree.fromstring(root_string)
    self.ocdid_validator = rules.ElectoralDistrictOcdId(election_tree, None)

    open_mod = inspect.getmodule(open)
    if "__builtins__" not in open_mod.__dict__.keys():
      # '__builtin__' for python2
      self.builtins_name = open_mod.__name__
    else:
      # 'builtins' for python3
      self.builtins_name = open_mod.__builtins__["__name__"]

    # mock open function call to read provided csv data
    downloaded_ocdid_file = "id,name\nocd-division/country:ar,Argentina"
    self.mock_open_func = mock_open(read_data=downloaded_ocdid_file)

  # _get_ocd_data tests
  def testParsesLocalCSVFileIfProvidedAndReturnsOCDIDs(self):
    # set local file so that countries_file is set to local
    self.ocdid_validator.local_file = "/path/to/file"

    with patch("{}.open".format(self.builtins_name), self.mock_open_func):
      codes = self.ocdid_validator._get_ocd_data()

    expected_codes = set(["ocd-division/country:ar"])

    self.assertEqual(1, self.mock_open_func.call_count)
    call_list = self.mock_open_func.call_args_list
    first_arg = call_list[0][0][0]
    self.assertEqual(first_arg, self.ocdid_validator.local_file)
    self.assertEqual(expected_codes, codes)

  # _verify_data tests
  def testItReturnsTrueWhenTheFileShasMatch(self):
    mock_sha1 = MagicMock
    mock_sha1.update = MagicMock()
    mock_sha1.hexdigest = MagicMock(return_value="abc123")

    mock_stat = MagicMock()
    self.ocdid_validator._get_latest_file_blob_sha = MagicMock(
        return_value="abc123")

    with patch("os.stat", mock_stat):
      with patch("hashlib.sha1", mock_sha1):
        with patch("io.open", self.mock_open_func):
          valid = self.ocdid_validator._verify_data("/usr/cache/country-ar.tmp")

    self.assertTrue(valid)
    self.assertEqual(3, mock_sha1.update.call_count)

  def testItReturnsFalseWhenTheFileShasDontMatch(self):
    mock_sha1 = MagicMock
    mock_sha1.update = MagicMock()
    mock_sha1.hexdigest = MagicMock(return_value="abc123")

    mock_stat = MagicMock()
    self.ocdid_validator._get_latest_file_blob_sha = MagicMock(
        return_value="abc456")

    with patch("os.stat", mock_stat):
      with patch("hashlib.sha1", mock_sha1):
        with patch("io.open", self.mock_open_func):
          valid = self.ocdid_validator._verify_data("/usr/cache/country-ar.tmp")

    self.assertFalse(valid)
    self.assertEqual(3, mock_sha1.update.call_count)


if __name__ == "__main__":
  absltest.main()
