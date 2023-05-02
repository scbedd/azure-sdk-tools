using System.Collections.Generic;
using System.CommandLine;
using System.CommandLine.Binding;

namespace Azure.Sdk.Tools.TestProxy.CommandOptions
{
    public class DefaultOptions
    {
        public string StorageLocation { get; set; }

        public string StoragePlugin { get; set; }

        // On the command line, use -- and everything after that becomes arguments to Host.CreateDefaultBuilder
        // For example Test-Proxy start -i -d -- --urls https://localhost:8002 would set AdditionaArgs to a list containing
        // --urls and https://localhost:8002 as individual entries. This is converted to a string[] before being
        // passed to Host.CreateDefaultBuilder
        public IEnumerable<string> AdditionalArgs { get; set; }
    }

    public class DefaultOptsBinder : BinderBase<DefaultOptions>
    {
        private readonly Option<string> _storageLocationOption;
        private readonly Option<string> _storagePluginOption;
        private readonly Argument<string[]> _additionalArgs;

        public DefaultOptsBinder(Option<string> storageLocationOption, Option<string> storagePluginOption, Argument<string[]> additionalArgs)
        {
            _storageLocationOption = storageLocationOption;
            _storagePluginOption = storagePluginOption;
            _additionalArgs = additionalArgs;
        }

        protected override DefaultOptions GetBoundValue(BindingContext bindingContext) =>
            new DefaultOptions
            {
                StorageLocation = bindingContext.ParseResult.GetValueForOption(_storageLocationOption),
                StoragePlugin = bindingContext.ParseResult.GetValueForOption(_storagePluginOption),
                AdditionalArgs = bindingContext.ParseResult.GetValueForArgument(_additionalArgs)
            };
    }
}
