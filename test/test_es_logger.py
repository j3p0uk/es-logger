# Copyright (c) 2018 Cisco Systems, Inc.
# All rights reserved.

__author__ = 'jonpsull'

import es_logger
import io
from jenkins import JenkinsException, NotFoundException
import nose
from parameterized import parameterized
import pkg_resources
import requests
from stevedore import ExtensionManager
import unittest.mock
import xml.etree.ElementTree as ET


class TestEsLogger(object):

    @unittest.mock.patch.dict(
        'os.environ', {'JENKINS_URL': 'jenkins_url', 'JENKINS_USER': 'jenkins_user',
                       'JENKINS_PASSWORD': 'jenkins_password', 'ES_JOB_NAME': 'es_job_name',
                       'ES_BUILD_NUMBER': '1000', 'PROCESS_CONSOLE_LOGS':
                       'process_console_logs1 process_console_logs2 process_console_logs3',
                       'GATHER_BUILD_DATA':
                       'gather_build_data1 gather_build_data2 gather_build_data3',
                       'GENERATE_EVENTS': 'generate_events1 generate_events2 generate_events3'})
    def setup(self):
        dep = pkg_resources.EntryPoint.parse(
            'dummy = test.test_plugins:DummyEventTarget')
        d = pkg_resources.Distribution()
        d._ep_map = {'es_logger.plugins.event_target': {'dummy': dep}}
        pkg_resources.working_set.add(d, 'dummy')
        ExtensionManager.ENTRY_POINT_CACHE = {}

        self.esl = es_logger.EsLogger(1000, ['dummy'])
        self.urls = {
            'get_build_env_vars': 'jenkins_url/job/job_name/1/injectedEnvVars/api/json?depth=1',
            'get_build_test_report': 'jenkins_url/job/job_name/1/testReport/api/json?depth=1'}

    @parameterized.expand(['get_build_env_vars', 'get_build_test_report'])
    def test_monkey_patch(self, param):
        with unittest.mock.patch('es_logger.jenkins.Jenkins.jenkins_open') as mock_open:
            self.esl.server.crumb = False
            mock_open.return_value = '{}'
            func = getattr(self.esl.server, param)
            func('job_name', 1, 1)
            request = mock_open.call_args[0][0]
            print("method: {} url: {} headers: {}".format(request.method, request.url,
                                                          request.headers))
            nose.tools.ok_(request.url == self.urls[param])

    @parameterized.expand(['get_build_env_vars', 'get_build_test_report'])
    def test_monkey_patch_missing(self, param):
        with unittest.mock.patch('es_logger.jenkins.Jenkins.jenkins_open') as mock_open:
            mock_open.return_value = None
            self.esl.server.crumb = False
            func = getattr(self.esl.server, param)
            nose.tools.assert_raises(JenkinsException,
                                     func, 'job_name', 1)

    @parameterized.expand(['get_build_env_vars', 'get_build_test_report'])
    def test_monkey_patch_http(self, param):
        with unittest.mock.patch('es_logger.jenkins.Jenkins.jenkins_open') as mock_open:
            mock_open.side_effect = requests.exceptions.HTTPError('url', 'code', 'msg', 'hdrs',
                                                                  unittest.mock.MagicMock())
            self.esl.server.crumb = False
            func = getattr(self.esl.server, param)
            nose.tools.assert_raises(JenkinsException,
                                     func, 'job_name', 1)

    @parameterized.expand(['get_build_env_vars', 'get_build_test_report'])
    def test_monkey_patch_value(self, param):
        with unittest.mock.patch('es_logger.jenkins.Jenkins.jenkins_open') as mock_open:
            mock_open.side_effect = ValueError()
            self.esl.server.crumb = False
            func = getattr(self.esl.server, param)
            nose.tools.assert_raises(JenkinsException,
                                     func, 'job_name', 1)

    @parameterized.expand(['get_build_env_vars', 'get_build_test_report'])
    def test_monkey_patch_not_found(self, param):
        with unittest.mock.patch('es_logger.jenkins.Jenkins.jenkins_open') as mock_open:
            mock_open.side_effect = NotFoundException()
            self.esl.server.crumb = False
            func = getattr(self.esl.server, param)
            ret = 'Return not set'
            ret = func('job_name', 1)
            nose.tools.ok_(ret is None,
                           "Return not None: {}".format(ret))

    @parameterized.expand(['jenkins_url', 'jenkins_user', 'jenkins_password', 'es_job_name'])
    def test_get(self, param):
        # Recreate the esl to validate parameters aren't set
        self.esl = es_logger.EsLogger(1000, ['dummy'])
        nose.tools.ok_(getattr(self.esl, param) is None,
                       "{} not None: {}".format(param, getattr(self.esl, param)))
        getter = getattr(self.esl, 'get_' + param)
        with unittest.mock.patch.dict('os.environ', {param.upper(): param}):
            setattr(self.esl, param, getter())
            nose.tools.ok_(getter() == param,
                           "{} returned {} not {}".format(getter.__name__, getter(), param))

    def test_get_es_build_number(self):
        # Recreate the esl to validate parameters aren't set
        self.esl = es_logger.EsLogger(1000, ['dummy'])
        nose.tools.ok_(self.esl.es_build_number == 0,
                       "self.esl.es_build_number not 0: {}".format(self.esl.es_build_number))
        with unittest.mock.patch.dict('os.environ', {'ES_BUILD_NUMBER': '1000'}):
            self.esl.es_build_number = self.esl.get_es_build_number()
            nose.tools.ok_(self.esl.get_es_build_number() == 1000,
                           "{} not returning {}".format(self.esl.get_es_build_number, 1000))

    @parameterized.expand(['process_console_logs', 'gather_build_data', 'generate_events'])
    def test_get_plugin(self, param):
        if param == 'generate_events':
            base = ['commit']
        else:
            base = []
        # Recreate the esl to validate parameters aren't set
        self.esl = es_logger.EsLogger(1000, ['dummy'])
        nose.tools.ok_(getattr(self.esl, param) == base,
                       "{} not []: {}".format(param, getattr(self.esl, param)))
        setattr(self.esl, param, None)
        getter = getattr(self.esl, 'get_' + param)
        with unittest.mock.patch.dict('os.environ',
                                      {param.upper(): "{}1 {}2 {}3".format(param, param, param)}):
            plugins = getter()
            expected = [param + '1', param + '2', param + '3'] + base
            nose.tools.ok_(plugins == expected,
                           "{} returned {} not {}".format(getter.__name__, getter(), expected))

    def test_list_plugins(self):
        dep = pkg_resources.EntryPoint.parse(
            'dummy = test.test_plugins:DummyConsoleLogProcessor')
        d = pkg_resources.Distribution()
        d._ep_map = {'es_logger.plugins.console_log_processor': {'dummy': dep}}
        pkg_resources.working_set.add(d, 'dummy')
        ExtensionManager.ENTRY_POINT_CACHE = {}
        self.esl.list_plugins()

    def test_list_plugins_data_only(self):
        dep = pkg_resources.EntryPoint.parse(
            'dummy = test.test_plugins:DummyConsoleLogProcessor')
        d = pkg_resources.Distribution()
        d._ep_map = {'es_logger.plugins.console_log_processor': {'dummy': dep}}
        pkg_resources.working_set.add(d, 'dummy')
        ExtensionManager.ENTRY_POINT_CACHE = {}
        self.esl.list_plugins(True, 'console_log_processor')

    def test_get_build_data(self):
        # Recreate the esl to validate parameters aren't set
        with unittest.mock.patch.dict(
                'os.environ', {'JENKINS_URL': 'jenkins_url', 'JENKINS_USER': 'jenkins_user',
                               'JENKINS_PASSWORD': 'jenkins_password', 'ES_JOB_NAME': 'es_job_name',
                               'ES_BUILD_NUMBER': '2', 'GATHER_BUILD_DATA': 'dummy'}):
            self.esl = es_logger.EsLogger(1000, ['dummy'])
        self.esl.es_build_number = '2'
        with unittest.mock.patch('stevedore.driver.DriverManager') as mock_driver_mgr, \
                unittest.mock.patch('jenkins.Jenkins.get_build_info') as mock_build_info, \
                unittest.mock.patch('jenkins.Jenkins.get_build_env_vars') as mock_env_vars, \
                unittest.mock.patch('jenkins.Jenkins.get_build_console_output') as mock_console, \
                unittest.mock.patch('jenkins.Jenkins.get_job_config') as mock_config:
            mock_env_vars.return_value = {'envMap': {'BUILD_NUMBER': '1',
                                                     'JOB_NAME': 'job_name',
                                                     'BUILD_URL': 'url',
                                                     'dummy': 'dummy'}}
            mock_build_info.return_value = {
                'description': 'description',
                'number': '1',
                'url': 'url',
                'actions': [{'_class': 'hudson.model.ParametersAction',
                             'parameters': [{'name': 'param', 'value': 'value'}]},
                            {'_class': 'hudson.plugins.git.util.BuildData',
                             'buildsByBranchName': {'b1': {'buildNumber': '1'},
                                                    'b2': {'buildNumber': '2'}},
                             'remoteUrls': ["repoURL"]}]}
            mock_console.return_value = 'log'

            config_xml = "<project></project>"
            mock_config.return_value = config_xml

            self.esl.get_build_data()
            mock_driver_mgr.assert_called_once()

            # Job Config recorded
            nose.tools.ok_(self.esl.es_info['job_config_info'].get("is_pipeline_job") is False,
                           "is_pipeline_job not '{}': {}".format(
                               False,
                               self.esl.es_info["job_config_info"]["is_pipeline_job"]))

            # The job_config is on of length 1.
            nose.tools.ok_(len(self.esl.es_info['job_config_info']) == 1,
                           "job_config_info len isn't '1': {}".format(
                               self.esl.es_info["job_config_info"]))

            # Console log recorded
            nose.tools.ok_(self.esl.es_info['console_log'] == 'log',
                           "console_log not 'log': {}".format(self.esl.es_info))
            # Parameters pulled out
            nose.tools.ok_(self.esl.es_info['parameters'].get('param') == 'value',
                           "Parameter 'param' not 'value': {}".format(self.esl.es_info))

            # Prevent ES field explosion through rewrite of builds by branch name
            nose.tools.ok_(
                self.esl.es_info['build_info']['actions'][1]['buildsByBranchName'] ==
                'Removed by es-logger',
                "buildsByBranchName not removed by es-logger: {}".format(self.esl.es_info))
            # Make sure the gather of the gather_build_data plugins was called
            nose.tools.ok_('dummy' in self.esl.es_info['build_data'].keys(),
                           "dummy not in build_data keys: {}".format(
                               self.esl.es_info))
            # SCM correctly processed
            nose.tools.ok_('repoURL' in self.esl.es_info['build_data'].keys(),
                           "repoURL not in build_data keys: {}".format(
                               self.esl.es_info['build_data']))

    def test_get_build_data_config_error(self):
        # Recreate the esl to validate parameters aren't set
        with unittest.mock.patch.dict(
                'os.environ', {'JENKINS_URL': 'jenkins_url', 'JENKINS_USER': 'jenkins_user',
                               'JENKINS_PASSWORD': 'jenkins_password', 'ES_JOB_NAME': 'es_job_name',
                               'ES_BUILD_NUMBER': '2', 'GATHER_BUILD_DATA': 'dummy'}):
            self.esl = es_logger.EsLogger(1000, ['dummy'])
        self.esl.es_build_number = '2'
        with unittest.mock.patch('stevedore.driver.DriverManager') as mock_driver_mgr, \
                unittest.mock.patch('jenkins.Jenkins.get_build_info') as mock_build_info, \
                unittest.mock.patch('jenkins.Jenkins.get_build_env_vars') as mock_env_vars, \
                unittest.mock.patch('jenkins.Jenkins.get_build_console_output') as mock_console, \
                unittest.mock.patch('jenkins.Jenkins.get_job_config') as mock_config:
            mock_env_vars.return_value = {'envMap': {'BUILD_NUMBER': '1',
                                                     'JOB_NAME': 'job_name',
                                                     'BUILD_URL': 'url',
                                                     'dummy': 'dummy'}}
            mock_build_info.return_value = {
                'description': 'description',
                'number': '1',
                'url': 'url',
                'actions': [{'_class': 'hudson.model.ParametersAction',
                             'parameters': [{'name': 'param', 'value': 'value'}]},
                            {'_class': 'hudson.plugins.git.util.BuildData',
                             'buildsByBranchName': {'b1': {'buildNumber': '1'},
                                                    'b2': {'buildNumber': '2'}},
                             'remoteUrls': ["repoURL"]}]}
            mock_console.return_value = 'log'
            mock_config.side_effect = JenkinsException("Error from Jenkins Api")

            self.esl.get_build_data()
            mock_driver_mgr.assert_called_once()

            # Job Config recorded
            expetected_error_msg = "Unable to retrieve config.xml."
            nose.tools.ok_(self.esl.es_info['job_config_info'] == expetected_error_msg,
                           "'job_config_info' value {} not '{}'".format(
                               self.esl.es_info['job_config_info'],
                               expetected_error_msg))

            # Console log recorded
            nose.tools.ok_(self.esl.es_info['console_log'] == 'log',
                           "console_log not 'log': {}".format(self.esl.es_info))
            # Parameters pulled out
            nose.tools.ok_(self.esl.es_info['parameters'].get('param') == 'value',
                           "Parameter 'param' not 'value': {}".format(self.esl.es_info))

            # Prevent ES field explosion through rewrite of builds by branch name
            nose.tools.ok_(
                self.esl.es_info['build_info']['actions'][1]['buildsByBranchName'] ==
                'Removed by es-logger',
                "buildsByBranchName not removed by es-logger: {}".format(self.esl.es_info))
            # Make sure the gather of the gather_build_data plugins was called
            nose.tools.ok_('dummy' in self.esl.es_info['build_data'].keys(),
                           "dummy not in build_data keys: {}".format(
                               self.esl.es_info))
            # SCM correctly processed
            nose.tools.ok_('repoURL' in self.esl.es_info['build_data'].keys(),
                           "repoURL not in build_data keys: {}".format(
                               self.esl.es_info['build_data']))

    def test_get_pipeline_job_type_script(self):
        script = "org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition"

        mock_job_xml = unittest.mock.MagicMock()
        mock_job_xml.find.return_value.attrib.__getitem__.return_value = script
        self.esl.job_xml = mock_job_xml

        test_result = self.esl.get_pipeline_job_type()

        mock_job_xml.find.assert_called_with("./definition")
        nose.tools.ok_(test_result == "Script",
                       "get_pipeline_job_type, returned: {}, expected {}".format(
                           test_result, "Script"))

    def test_get_pipeline_job_type_scm(self):
        scm = "org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition"
        mock_job_xml = unittest.mock.MagicMock()
        mock_job_xml.find.return_value.attrib.__getitem__.return_value = scm
        self.esl.job_xml = mock_job_xml

        test_result = self.esl.get_pipeline_job_type()

        mock_job_xml.find.assert_called_with("./definition")
        nose.tools.ok_(test_result == "SCM",
                       "get_pipeline_job_type, returned: {}, expected {}".format(
                           test_result, "SCM"))

    def test_get_pipeline_job_type_multibranch(self):
        multibranch = "org.jenkinsci.plugins.workflow.multibranch.SCMBinder"
        mock_job_xml = unittest.mock.MagicMock()
        mock_job_xml.find.return_value.attrib.__getitem__.return_value = multibranch
        self.esl.job_xml = mock_job_xml

        test_result = self.esl.get_pipeline_job_type()

        mock_job_xml.find.assert_called_with("./definition")
        nose.tools.ok_(test_result == "Multibranch",
                       "get_pipeline_job_type, returned: {}, expected {}".format(
                           test_result, "Multibranch"))

    def test_get_pipeline_job_type_invalid(self):
        mock_job_xml = unittest.mock.MagicMock()
        mock_job_xml.find.return_value.attrib.__getitem__.return_value = "blah"
        self.esl.job_xml = mock_job_xml

        test_result = self.esl.get_pipeline_job_type()
        mock_job_xml.find.assert_called_with("./definition")
        nose.tools.ok_(test_result == "Unknown",
                       "get_pipeline_job_type, returned: {}, expected {}".format(
                           test_result, "Unknown"))

    def test_get_pipeline_job_type_not_pipeline_job(self):
        self.esl.job_xml = "Not a pipeline job"

        test_result = self.esl.get_pipeline_job_type()
        nose.tools.ok_(test_result == "Unknown",
                       "get_pipeline_job_type, returned: {}, expected {}".format(
                           test_result, "Unknown"))

    def test_get_pipeline_job_type_config_xml_is_none(self):
        test_result = self.esl.get_pipeline_job_type()
        nose.tools.ok_(test_result is None,
                       "get_pipeline_job_type, returned: {}, expected {}".format(
                           test_result, None))

    def test_get_pipeline_job_info_not_pipeline(self):
        test_mock = unittest.mock.Mock()
        test_mock.tag = "Random tag"
        self.esl.job_xml = test_mock

        test_result = self.esl.get_pipeline_job_info()

        nose.tools.ok_(test_result == {"is_pipeline_job": False},
                       "get_pipeline_job_info, returned: {}, expected {}".format(
                           test_result, {"is_pipeline_job": False}))

    def test_get_pipeline_job_info_unknown_pipeline(self):
        unknown_pipeline_xml = """
            <flow-definition plugin="workflow-job@2.29">
                <definition class="What is this?"></definition>
            </flow-definition>"""
        self.esl.job_xml = ET.fromstring(unknown_pipeline_xml)

        test_result = self.esl.get_pipeline_job_info()

        expected_result = {"is_pipeline_job": True,
                           "pipeline_job_type": "Unknown"}

        nose.tools.ok_(test_result == expected_result,
                       "get_pipeline_job_info, returned: {}, expected {}".format(
                           test_result, expected_result))

    def test_get_pipeline_job_info_pipeline_script(self):
        pipeline_script_xml = """
            <flow-definition plugin="workflow-job@2.29">
                <definition class="org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition"
                        plugin="workflow-cps@2.46">
                </definition>
            </flow-definition>"""
        self.esl.job_xml = ET.fromstring(pipeline_script_xml)

        test_result = self.esl.get_pipeline_job_info()
        expected_result = {"is_pipeline_job": True,
                           "pipeline_job_type": "Script"}

        nose.tools.ok_(test_result == expected_result,
                       "get_pipeline_job_info, returned: {}, expected {}".format(
                           test_result, expected_result))

    def test_get_pipeline_job_info_pipeline_scm_not_git(self):
        pipeline_scm_not_git_xml = """
            <flow-definition plugin="workflow-job@2.29">
                <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition"
                        plugin="workflow-cps@2.46">
                    <scm class="Not Git" plugin="something else">
                    </scm>
                    <scriptPath>JenkinsfileName</scriptPath>
                </definition>
            </flow-definition>"""
        self.esl.job_xml = ET.fromstring(pipeline_scm_not_git_xml)

        test_result = self.esl.get_pipeline_job_info()
        expected_result = {"is_pipeline_job": True,
                           "pipeline_job_type": "SCM",
                           "jenkinsfile": "JenkinsfileName"}

        nose.tools.ok_(test_result == expected_result,
                       "get_pipeline_job_info, returned: {}, expected {}".format(
                           test_result, expected_result))

    def test_get_pipeline_job_info_pipeline_scm_git(self):
        pipeline_scm_git_xml = """
            <flow-definition plugin="workflow-job@2.29">
                <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition"
                        plugin="workflow-cps@2.46">
                    <scm class="hudson.plugins.git.GitSCM" plugin="git@3.9.1">
                        <userRemoteConfigs>
                            <hudson.plugins.git.UserRemoteConfig>
                                <url>git_repo_addr</url>
                            </hudson.plugins.git.UserRemoteConfig>
                        </userRemoteConfigs>
                        <branches>
                            <hudson.plugins.git.BranchSpec>
                                <name>branch_string</name>
                            </hudson.plugins.git.BranchSpec>
                        </branches>
                    </scm>
                    <scriptPath>JenkinsfileName</scriptPath>
                </definition>
            </flow-definition>"""
        self.esl.job_xml = ET.fromstring(pipeline_scm_git_xml)

        test_result = self.esl.get_pipeline_job_info()
        expected_result = {"is_pipeline_job": True,
                           "pipeline_job_type": "SCM",
                           "jenkinsfile": "JenkinsfileName",
                           "git_repo": "git_repo_addr",
                           "git_branch": "branch_string"}

        nose.tools.ok_(test_result == expected_result,
                       "get_pipeline_job_info, returned: {}, expected {}".format(
                           test_result, expected_result))

    def test_get_pipeline_job_info_pipeline_multibranch_no_git(self):
        pipeline_multibranch_not_git_xml = """
            <flow-definition plugin="workflow-job@2.29">
                <properties>
                    <org.jenkinsci.plugins.workflow.multibranch.BranchJobProperty
                                   plugin="workflow-multibranch@2.20">
                        <branch plugin="branch-api@2.0.20.1">
                            <scm class="Not Git" plugin="something else">
                            </scm>
                        </branch>
                    </org.jenkinsci.plugins.workflow.multibranch.BranchJobProperty>
                </properties>
                <definition class="org.jenkinsci.plugins.workflow.multibranch.SCMBinder"
                            plugin="workflow-multibranch@2.20">
                    <scriptPath>JenkinsfileName</scriptPath>
                </definition>
            </flow-definition>"""
        self.esl.job_xml = ET.fromstring(pipeline_multibranch_not_git_xml)

        test_result = self.esl.get_pipeline_job_info()
        expected_result = {"is_pipeline_job": True,
                           "pipeline_job_type": "Multibranch",
                           "jenkinsfile": "JenkinsfileName"}

        nose.tools.ok_(test_result == expected_result,
                       "get_pipeline_job_info, returned: {}, expected {}".format(
                           test_result, expected_result))

    def test_get_pipeline_job_info_pipeline_multibranch_git(self):
        pipeline_multibranch_git_xml = """
            <flow-definition plugin="workflow-job@2.29">
                <properties>
                    <org.jenkinsci.plugins.workflow.multibranch.BranchJobProperty
                                   plugin="workflow-multibranch@2.20">
                        <branch plugin="branch-api@2.0.20.1">
                            <scm class="hudson.plugins.git.GitSCM" plugin="git@3.9.3">
                                <userRemoteConfigs>
                                    <hudson.plugins.git.UserRemoteConfig>
                                        <url>git_repo_addr</url>
                                    </hudson.plugins.git.UserRemoteConfig>
                                </userRemoteConfigs>
                                <branches class="singleton-list">
                                    <hudson.plugins.git.BranchSpec>
                                        <name>branch_string</name>
                                    </hudson.plugins.git.BranchSpec>
                                </branches>
                            </scm>
                        </branch>
                    </org.jenkinsci.plugins.workflow.multibranch.BranchJobProperty>
                </properties>
                <definition class="org.jenkinsci.plugins.workflow.multibranch.SCMBinder"
                            plugin="workflow-multibranch@2.20">
                    <scriptPath>JenkinsfileName</scriptPath>
                </definition>
            </flow-definition>"""
        self.esl.job_xml = ET.fromstring(pipeline_multibranch_git_xml)

        test_result = self.esl.get_pipeline_job_info()
        expected_result = {"is_pipeline_job": True,
                           "pipeline_job_type": "Multibranch",
                           "jenkinsfile": "JenkinsfileName",
                           "git_repo": "git_repo_addr",
                           "git_branch": "branch_string"}

        nose.tools.ok_(test_result == expected_result,
                       "get_pipeline_job_info, returned: {}, expected {}".format(
                           test_result, expected_result))

    def test_get_pipeline_job_info_config_xml_is_none(self):
        test_result = self.esl.get_pipeline_job_info()
        nose.tools.ok_(test_result == {},
                       "get_pipeline_job_info, returned: {}, expected {}".format(
                           test_result, {}))

    def test_process_build_info_actions_no_key_error(self):
        self.esl.es_info = {'build_info': {'actions': [
            {'_class': 'hudson.model.ParametersAction', 'parameters': [{'name': 'param'}]}]}}
        self.esl.process_build_info()

    # This is tested through get of the build data above
    def test_process_build_info(self):
        pass

    def test_process_console_log(self):
        self.esl.process_console_logs = ['dummy']
        with unittest.mock.patch('stevedore.driver.DriverManager') as mock_driver_mgr:
            with unittest.mock.patch('jenkins.Jenkins.get_build_console_output') as mock_get:
                mock_get.return_value = 'log'
                self.esl.process_console_log()
                mock_driver_mgr.assert_called_once()
                self.esl.console_length = 1
                mock_get.return_value = 'log'
                self.esl.process_console_log()
                nose.tools.ok_(len(self.esl.es_info['console_log']) == 1,
                               "Console log length not 1: {}".format(
                                    self.esl.es_info['console_log']))

    # Tested in get_events
    def test_get_event_info(self):
        pass

    def test_get_events(self):
        self.esl.generate_events = ['dummy']
        self.esl.es_info['env_vars'] = {'envMap': {'BUILD_NUMBER': '1',
                                                   'JOB_NAME': 'job_name',
                                                   'BUILD_URL': 'url',
                                                   'dummy': 'dummy'}}
        self.esl.es_info['build_info'] = {'description': 'description',
                                          'number': '1',
                                          'url': 'url'}
        self.esl.es_info['parameters'] = {'parameter': 'parameter'}
        self.esl.es_info[self.esl.data_name]['job_name'] = 'job_name'
        self.esl.es_info[self.esl.data_name]['jenkins_url'] = 'url'
        with unittest.mock.patch('stevedore.driver.DriverManager') as mock_driver_mgr:
            mock_driver_mgr().driver.get_fields.return_value = 'dummy'
            mock_driver_mgr().driver.generate_events.return_value = [{'DummyEventGenerator': 1},
                                                                     {'DummyEventGenerator': 2}]
            self.esl.get_events()
            nose.tools.ok_(mock_driver_mgr.call_count == 3,
                           "Incorrect call count: {}".format(mock_driver_mgr.call_count))
            nose.tools.ok_(len(self.esl.events) == 2,
                           "Incorrect number of events: {}".format(self.esl.events))
            nose.tools.ok_('timestamp' in self.esl.events[0]['build_info'].keys(),
                           "No timestamp in event: {}".format(
                                self.esl.events[0]['build_info'].keys()))
            for field in self.esl.build_info_fields:
                for count in range(2):
                    nose.tools.ok_(self.esl.events[count]['build_info'][field] ==
                                   self.esl.es_info['build_info'][field],
                                   "Incorrect {} in event {} build_info: {}".format(
                                        self.esl.events[count]['build_info'][field], count,
                                        self.esl.es_info['build_info'][field]))
                    nose.tools.ok_(self.esl.events[count]['build_info'][field] ==
                                   self.esl.events[count][field],
                                   "Incorrect {} in event {} build_info: {}".format(
                                        self.esl.events[count]['build_info'][field], count,
                                        self.esl.events[count][field]))

    def test_gather_all(self):
        with unittest.mock.patch('es_logger.EsLogger.get_build_data') as mock_get_build_data, \
                unittest.mock.patch('es_logger.EsLogger.get_events') as mock_get_events:
            self.esl.gather_all()
            mock_get_build_data.assert_called_once()
            mock_get_events.assert_called_once()

    def test_post_all(self):
        with unittest.mock.patch('es_logger.EsLogger.post') as mock_post, \
                unittest.mock.patch('es_logger.EsLogger.finish') as mock_finish:
            self.esl.post_all()
            mock_post.assert_called_once()
            mock_finish.assert_called_once()

    def test_get_test_report(self):
        with unittest.mock.patch('jenkins.Jenkins.get_build_test_report') as mock_get:
            self.esl.get_test_report()
            mock_get.assert_called_once()
        nose.tools.ok_(self.esl.es_info['test_report'] is not None,
                       "Test report is None: {}".format(self.esl.es_info['test_report']))

    def test_dump(self):
        with unittest.mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            self.esl.dump({"event": "event"})
        print(mock_stdout.getvalue())
        nose.tools.ok_(mock_stdout.getvalue() == '{\n  "event": "event"\n}\n',
                       "Incorrect output:\n{}".format(mock_stdout.getvalue()))

    def test_post(self):
        status = self.esl.post({"es-logger": True})
        nose.tools.ok_(status == 0)

    def test_post_bad(self):
        status = self.esl.post(None)
        nose.tools.ok_(status == 1)

    def test_finish(self):
        status = self.esl.finish()
        nose.tools.ok_(status == 0)

    def test_finish_bad(self):
        mock_target = unittest.mock.MagicMock()
        mock_target.driver.finish_send.return_value = 1
        self.esl.targets = [mock_target, mock_target]
        status = self.esl.finish()
        nose.tools.ok_(status == 2)
