$pythonTablesIn = "C:/repo/sdk-for-python/sdk/tables/azure-data-tables/tests/recordings/"
$pythonTablesOut = "C:/repo/sdk-tools/tools/oav-traffic-converter/output-example/python/tables"
$swagger = "C:/repo/azure-rest-api-specs/specification/cosmos-db/data-plane/Microsoft.Tables/preview/2019-02-02/table.json"


oavc convert --directory $pythonTablesIn --out $pythonTablesOut
oav validate-traffic $pythonTablesOut $swagger -l error > validate-traffic.txt


$trafficData = gc "./validate-traffic.txt"
$trafficData | % { $_ -Replace "^}$","}," }
Set-Content "validation-traffic-json.txt" $trafficData