// 最简测试：验证JSX脚本执行功能
(function() {
    var f = new File("C:/Users/Administrator/Desktop/AE-Knowledge-Vault/output_director/ae_project_analysis/jsx_test.txt");
    f.encoding = "UTF-8";
    f.open("w");
    f.write("JSX is working! Time: " + new Date().toString());
    f.close();
})();
