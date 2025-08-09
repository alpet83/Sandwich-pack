<?php
  // /tests/test.php, updated 2025-08-02 13:35 EEST
  // PHP test file with various entities
  
  // Regular function
  function simple_function() {
      echo "";
  }
  
  // Class with methods
  class MyClass {
      public function my_method() {
          imported_func();
      }
      public function sqli(): ?mysqli_ex {
          return null;
      }
      public function my_abstract_method();
  }
  
  // Imports
  require "my_module.php";
?>
Not a code trap
function fake_function() {
}
<?PHP
// Next block 
  function last_function(a = "" + 'delta') {
  }
?>