using CommandLine.Text;
using CommandLine;

namespace Azure.Sdk.Tools.TestProxy.CommandParserOptions
{
    /// <summary>
    /// Any unique options to the push command will reside here.
    /// </summary>
    [Verb("cd", HelpText = "Change directory to the assets folder for a given assets.json.")]
    class CdOptions : CLICommandOptions
    {

    }
}
