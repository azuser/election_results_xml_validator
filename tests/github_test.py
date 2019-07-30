"""Unit tests for rules.py that leverage the github dependency."""

import datetime
import inspect
import time

from absl.testing import absltest
from election_results_xml_validator import rules
import github
from lxml import etree
from mock import create_autospec
from mock import MagicMock
from mock import mock_open
from mock import patch


class ElectoralDistrictOcdIdGithubTest(absltest.TestCase):

  def setUp(self):
    super(ElectoralDistrictOcdIdGithubTest, self).setUp()
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
      # "__builtin__" for python2
      self.builtins_name = open_mod.__name__
    else:
      # "builtins" for python3
      self.builtins_name = open_mod.__builtins__["__name__"]

    # mock open function call to read provided csv data
    downloaded_ocdid_file = "id,name\nocd-division/country:ar,Argentina"
    self.mock_open_func = mock_open(read_data=downloaded_ocdid_file)

  # _get_ocd_data tests
  def testDownloadsDataIfNoLocalFileAndNoCachedFile(self):
    # mock os call to return file path to be used for countries_file
    mock_expanduser = MagicMock(return_value="/usr/cache")
    # 1st call checks for existence of countries_file - return false
    # 2nd call to os.path.exists check for cache directory - return true
    mock_exists = MagicMock(side_effect=[False, True])

    # stub out live call to github api
    mock_github = create_autospec(github.Github)
    mock_github.get_repo = MagicMock()

    self.ocdid_validator.github_file = "country-ar.csv"
    self.ocdid_validator._download_data = MagicMock()

    with patch("os.path.expanduser", mock_expanduser):
      with patch("os.path.exists", mock_exists):
        with patch("github.Github", mock_github):
          with patch("{}.open".format(self.builtins_name), self.mock_open_func):
            codes = self.ocdid_validator._get_ocd_data()

    expected_codes = set(["ocd-division/country:ar"])

    self.assertTrue(mock_github.get_repo.called_with(
        self.ocdid_validator.GITHUB_REPO))
    self.assertTrue(self.ocdid_validator._download_data.called_with(
        "/usr/cache/country-ar.csv"))
    self.assertEqual(expected_codes, codes)

  def testDownloadsDataIfCachedFileIsStale(self):
    # mock os call to return file path to be used for countries_file
    mock_expanduser = MagicMock(return_value="/usr/cache")
    # call to os.path.exists checks for existence of countries_file-return True
    mock_exists = MagicMock(return_value=True)

    # set modification date to be over an hour behind current time
    stale_time = datetime.datetime.now() - datetime.timedelta(minutes=62)
    mock_timestamp = time.mktime(stale_time.timetuple())
    mock_getmtime = MagicMock(return_value=mock_timestamp)

    # stub out live call to github api
    mock_github = create_autospec(github.Github)
    mock_github.get_repo = MagicMock()

    # mock update time function on countries file to make sure it's being called
    mock_utime = MagicMock()

    self.ocdid_validator.github_file = "country-ar.csv"
    self.ocdid_validator._download_data = MagicMock()
    self.ocdid_validator._get_latest_commit_date = MagicMock(
        return_value=datetime.datetime.now())

    with patch("os.path.expanduser", mock_expanduser):
      with patch("os.path.exists", mock_exists):
        with patch("github.Github", mock_github):
          with patch("{}.open".format(self.builtins_name), self.mock_open_func):
            with patch("os.path.getmtime", mock_getmtime):
              with patch("os.utime", MagicMock()):
                codes = self.ocdid_validator._get_ocd_data()

    expected_codes = set(["ocd-division/country:ar"])

    self.assertTrue(mock_github.get_repo.called_with(
        self.ocdid_validator.GITHUB_REPO))
    self.assertTrue(self.ocdid_validator._get_latest_commit_date.called_once)
    self.assertTrue(mock_utime.called_once)
    self.assertTrue(self.ocdid_validator._download_data.called_with(
        "/usr/cache/country-ar.csv"))
    self.assertEqual(expected_codes, codes)

  # _get_latest_commit_date tests
  def testReturnsTheLatestCommitDateForTheCountryCSV(self):
    self.ocdid_validator.github_file = "country-ar.csv"
    self.ocdid_validator.github_repo = github.Repository.Repository(
        None, [], [], None)

    now = datetime.datetime.now()
    formatted_commit_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    commit = github.Commit.Commit(None, {}, dict({
        "commit": dict({
            "committer": dict({
                "date": formatted_commit_date
            })
        })
    }), None)

    mock_get_commits = MagicMock(return_value=[commit])
    self.ocdid_validator.github_repo.get_commits = mock_get_commits

    latest_commit_date = self.ocdid_validator._get_latest_commit_date()
    self.assertEqual(now.replace(microsecond=0), latest_commit_date)
    mock_get_commits.assert_called_with(path="identifiers/country-ar.csv")

  # _get_latest_file_blob_sha tests
  def testItReturnsTheBlobShaOfTheGithubFileWhenFound(self):
    content_file = github.ContentFile.ContentFile(None, {}, dict({
        "name": "country-ar.csv", "sha": "abc123"
    }), None)
    repo = github.Repository.Repository(None, {}, {}, None)
    repo.get_dir_contents = MagicMock(return_value=[content_file])
    self.ocdid_validator.github_repo = repo
    self.ocdid_validator.github_file = "country-ar.csv"

    blob_sha = self.ocdid_validator._get_latest_file_blob_sha()
    self.assertEqual("abc123", blob_sha)

  def testItReturnsNoneIfTheFileCantBeFound(self):
    content_file = github.ContentFile.ContentFile(None, {}, dict({
        "name": "country-ar.csv", "sha": "abc123"
    }), None)
    repo = github.Repository.Repository(None, {}, {}, None)
    repo.get_dir_contents = MagicMock(return_value=[content_file])
    self.ocdid_validator.github_repo = repo
    self.ocdid_validator.github_file = "country-us.csv"

    blob_sha = self.ocdid_validator._get_latest_file_blob_sha()
    self.assertIsNone(blob_sha)


if __name__ == "__main__":
  absltest.main()
