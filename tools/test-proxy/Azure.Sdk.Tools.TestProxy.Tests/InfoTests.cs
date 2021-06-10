﻿using Azure.Sdk.Tools.TestProxy.Models;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Xunit;

namespace Azure.Sdk.Tools.TestProxy.Tests
{
    public class InfoTests
    {
        [Fact]
        public void TestReflectionModelBuild()
        {
            var testModel = new CommonMetadataModel();

            // in general, check that these are populating correctly
            Assert.True(testModel.Sanitizers.Count() > 0);
            Assert.True(testModel.Matchers.Count() > 0);
            Assert.True(testModel.Transforms.Count() > 0);

            // double check to ensure that an class constructor descriptions and class description are populated properly from xml. 
            var documentedSanitizer = testModel.Sanitizers.First();
            var sampleArgTuple = documentedSanitizer.Arguments.First();
            Assert.True(!String.IsNullOrEmpty(documentedSanitizer.Description));
            Assert.True(!String.IsNullOrEmpty(sampleArgTuple.Item2));
        }
    }
}
