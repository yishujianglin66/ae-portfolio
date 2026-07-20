(function() {
    var f = new File("C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/test_r_flag.log");
    f.encoding = "UTF-8";
    f.open("w");
    f.write("AE started with -r flag successfully at " + new Date().toString());
    f.close();
})();
