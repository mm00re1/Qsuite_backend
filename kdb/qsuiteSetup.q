
if[not count key `.qsuite.test; .qsuite.tests:enlist[`]!enlist (::)];

.qsuite.showAllTests:{[]
    string (key `.qsuite.tests) except `
 };

.qsuite.showAllSubTests:{[]
    string (key `.qsuite.subTests) except `
 };

.qsuite.showMatchingTests:{[pattern]
    string (key[`.qsuite.tests] where key[`.qsuite.tests] like "*",pattern,"*") except `
 };

.qsuite.showMatchingSubTests:{[pattern]
    string (key[`.qsuite.subTests] where key[`.qsuite.subTests] like "*",pattern,"*") except `
 };

.qsuite.parseTestCode:{[testName]
    fullName: ` sv `.qsuite.tests, `$testName;
    .Q.s1 get fullName
 };

.qsuite.executeUserCode:{[code]
    .debug.code: code;
    // qFunction = '{[] ' + ''.join(code) + '}'
    res:@[value; code; {x}];
    // block from parsing result greater than 1MB in size, users can view head of result if necessary ie 10#table
    $[1000000 < -22!res; "can't return preview of objects this large"; res]
 };

.qsuite.executeFunction:{[testName]
    fullName: ` sv `.qsuite.tests, `$testName;
    res:@[get fullName; ::; {x}];
    // block from parsing result greater than 1MB in size, users can view head of result if necessary ie 10#table
    $[1000000 < -22!res; "can't return preview of objects this large"; res]
 };

.qsuite.tests.test1:{[] 
    cntQuote:count select from quote;
    cntQuote > 100
 };

.qsuite.tests.test2:{[] 
    cntQuote:count select from quote;
    cntQuote > 100
 };

.qsuite.tests.test3:{[] 
    cntQuote:count select from quote;
    cntQuote > 100
 };

.qsuite.tests.test4:{[] 
    cntQuote:count select from quote;
    cntQuote > 100
 };

.qsuite.tests.test5:{[] 
    cntQuote:count select from quote;
    cntQuote > 100
 };

.qsuite.tests.test6:{[] 
    cntQuote:count select from quote;
    cntQuote > 100
 };

.qsuite.tests.test7:{[] 
    cntQuote:count select from quote;
    cntQuote > 100
 };

.qsuite.tests.test8:{[] 
    cntQuote:count select from quote;
    cntQuote > 100
 };

.qsuite.tests.test9:{[] 
    cntQuote:count select from quote;
    cntQuote > 100
 };

.qsuite.tests.test10:{[] 
    cntQuote:count select from quote;
    cntQuote > 100
 };

.qsuite.tests.test11:{[] 
    cntQuote:count select from quote;
    cntQuote > 100
 };

.qsuite.subTests.sub: .u.sub;
