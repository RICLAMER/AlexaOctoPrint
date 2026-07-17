$(function () {
    function AlexaOctoPrintViewModel(parameters) {
        var self = this;

        self.settings = parameters[0];
        self.debugStatus = ko.observable(null);
        self.files = ko.observableArray([{ label: "-", path: "" }]);
        self.actionList = ko.observableArray([]);
        self.enclosureStatus = ko.observable(null);
        self.enclosureLabels = ko.observableArray([]);
        self.proxyStatus = ko.observable(null);
        self.emptySetting = ko.observable();

        self.pluginSettings = function () {
            return self.settings.settings.plugins.alexaoctoprint;
        };

        self.actionSetting = function (action, key) {
            var pluginSettings = self.pluginSettings();
            if (!pluginSettings || !pluginSettings.actions || !pluginSettings.actions[action.key]) {
                return self.emptySetting;
            }
            if (pluginSettings.actions[action.key][key] === undefined) {
                return self.emptySetting;
            }
            return pluginSettings.actions[action.key][key];
        };

        self.hasSetting = function (action, key) {
            var pluginSettings = self.pluginSettings();
            return !!(
                pluginSettings &&
                pluginSettings.actions &&
                pluginSettings.actions[action.key] &&
                pluginSettings.actions[action.key][key] !== undefined
            );
        };

        self.enclosureAvailable = ko.pureComputed(function () {
            var status = self.enclosureStatus();
            return !!(status && status.available);
        });

        self.proxyStatusText = ko.pureComputed(function () {
            var status = self.proxyStatus();
            if (!status) {
                return "";
            }
            var lines = [
                status.message || status.error || status.status || ""
            ];
            if (status.port_80 && status.port_80.process) {
                lines.push("Port 80: " + status.port_80.process + " " + (status.port_80.address || ""));
            }
            if (status.backup_path) {
                lines.push("Backup: " + status.backup_path);
            }
            if (status.ssh_required) {
                lines.push("SSH permission setup required.");
            }
            return lines.join("\n");
        });

        self.refreshDebug = function () {
            return OctoPrint.simpleApiCommand("alexaoctoprint", "debug_status", {})
                .done(function (response) {
                    self.debugStatus(response);
                    if (response.actions) {
                        self.actionList(response.actions);
                    }
                    if (response.enclosure) {
                        self.setEnclosureStatus(response.enclosure);
                    }
                });
        };

        self.setEnclosureStatus = function (response) {
            var options = (response.outputs || []).slice();
            var pluginSettings = self.pluginSettings();
            _.each((pluginSettings && pluginSettings.actions) || {}, function (action) {
                if (!action.enclosure_label) {
                    return;
                }
                var configured = ko.unwrap(action.enclosure_label);
                if (!configured) {
                    return;
                }
                var matchingOutput = _.find(options, function (output) {
                    return String(output.label).toLowerCase() === String(configured).toLowerCase();
                });
                if (matchingOutput) {
                    action.enclosure_label(matchingOutput.label);
                } else {
                    options.push({ label: configured });
                }
            });
            self.enclosureStatus(response);
            self.enclosureLabels(options);
        };

        self.refreshEnclosure = function () {
            return OctoPrint.simpleApiCommand("alexaoctoprint", "list_enclosure_outputs", {})
                .done(self.setEnclosureStatus);
        };

        self.refreshFiles = function () {
            return OctoPrint.simpleApiCommand("alexaoctoprint", "list_files", {})
                .done(function (response) {
                    var options = [{ label: "-", path: "" }];
                    _.each(response.files || [], function (file) {
                        options.push({
                            label: file.origin + ": " + file.name,
                            path: file.path,
                            origin: file.origin
                        });
                    });
                    self.files(options);
                });
        };

        self.notifyResult = function (response, fallback) {
            new PNotify({
                title: response.ok ? "Alexa OctoPrint" : "Alexa OctoPrint error",
                text: response.message || response.error || fallback,
                type: response.ok ? "success" : "error",
                hide: true
            });
        };

        self.runAction = function (action, requestedOn) {
            return OctoPrint.simpleApiCommand("alexaoctoprint", "run_action", {
                action: action.key,
                on: requestedOn
            }).done(function (response) {
                self.notifyResult(response, action.key);
                self.refreshDebug();
            });
        };

        self.runActionOn = function (action) {
            return self.runAction(action, true);
        };

        self.runActionOff = function (action) {
            return self.runAction(action, false);
        };

        self.refreshProxyStatus = function (notify) {
            return OctoPrint.simpleApiCommand("alexaoctoprint", "proxy_status", {})
                .done(function (response) {
                    self.proxyStatus(response);
                    if (notify) {
                        self.notifyResult(response, "HAProxy status");
                    }
                });
        };

        self.inspectProxy = function () {
            return self.refreshProxyStatus(true);
        };

        self.runProxyChange = function (command, confirmation) {
            if (!window.confirm(confirmation)) {
                return;
            }
            return OctoPrint.simpleApiCommand("alexaoctoprint", command, {})
                .done(function (response) {
                    self.proxyStatus(response);
                    self.notifyResult(response, command);
                    self.refreshDebug();
                });
        };

        self.installProxy = function () {
            return self.runProxyChange(
                "proxy_install",
                "Inspect port 80, back up HAProxy, add only Alexa OctoPrint routes, validate, and restart HAProxy?"
            );
        };

        self.removeProxy = function () {
            return self.runProxyChange(
                "proxy_remove",
                "Restore the HAProxy configuration saved before Alexa OctoPrint setup?"
            );
        };

        self.onBeforeBinding = function () {
            self.refreshDebug();
            self.refreshFiles();
            self.refreshEnclosure();
            self.refreshProxyStatus(false);
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: AlexaOctoPrintViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#settings_plugin_alexaoctoprint"]
    });
});
